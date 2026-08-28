#!/usr/bin/env python3
"""
pixi_task_runner.py

Run pixi tasks from either:
  - pixi.toml:        [tasks]
  - pyproject.toml:   [tool.pixi.tasks]

Usage:
  python pixi_task_runner.py help
  python pixi_task_runner.py <task> [args...]
  python pixi_task_runner.py <command> [args...]

Env:
  PIXI_MANIFEST   optional explicit path to pixi.toml or pyproject.toml
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _toml_load(path: Path) -> Dict[str, Any]:
    """
    Load TOML from a file path.

    - tomllib (py>=3.11): expects str
    - tomli (backport): expects str
    """
    text = path.read_text(encoding="utf-8")

    # Prefer stdlib when available
    try:
        import tomllib  # py>=3.11
        return tomllib.loads(text)
    except Exception:
        pass

    try:
        import tomli  # type: ignore
        return tomli.loads(text)
    except Exception as e:
        raise RuntimeError(
            "No TOML parser available. Use Python 3.11+ (tomllib) "
            "or include tomli in the environment."
        ) from e

def _find_manifest(start: Path) -> Optional[Path]:
    """
    Search upward from start for pixi.toml or pyproject.toml.
    Prefer pixi.toml if both exist (Pixi precedence).
    """
    cur = start.resolve()
    for d in [cur, *cur.parents]:
        p1 = d / "pixi.toml"
        if p1.exists():
            return p1
        p2 = d / "pyproject.toml"
        if p2.exists():
            return p2
    return None


def _extract_tasks(manifest_path: Path, data: Dict[str, Any]) -> Dict[str, Any]:
    if manifest_path.name == "pixi.toml":
        return data.get("tasks", {}) or {}
    if manifest_path.name == "pyproject.toml":
        return (
            (data.get("tool") or {})
            .get("pixi", {})
            .get("tasks", {})
            or {}
        )
    # fallback: try both
    return data.get("tasks", {}) or (
        (data.get("tool") or {}).get("pixi", {}).get("tasks", {}) or {}
    )


def _normalize_dep_entry(entry: Any) -> Tuple[str, List[str], Optional[str], Dict[str, str]]:
    """
    Normalize a dependency entry into (task_name, args, cwd, env_overrides).
    Supports:
      - "fmt"
      - { task = "fmt" }
      - { task = "fmt", args = ["--fix"], cwd = "scripts", env = { ... } }
    """
    if isinstance(entry, str):
        return entry, [], None, {}
    if isinstance(entry, dict):
        t = entry.get("task")
        if not isinstance(t, str) or not t:
            raise ValueError(f"Invalid depends-on entry (missing task): {entry}")
        args = entry.get("args") or []
        if isinstance(args, str):
            args = [args]
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError(f"Invalid args in depends-on entry: {entry}")
        cwd = entry.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError(f"Invalid cwd in depends-on entry: {entry}")
        env = entry.get("env") or {}
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise ValueError(f"Invalid env in depends-on entry: {entry}")
        return t, args, cwd, env
    raise ValueError(f"Unsupported depends-on entry type: {type(entry)}")


def _task_def_to_spec(taskdef: Any) -> Tuple[Optional[Any], List[Any], Optional[str], Dict[str, str]]:
    """
    Returns (cmd, deps, cwd, env)

    taskdef forms:
      - "cmd ..."
      - { cmd = "...", depends-on = [...], cwd = "...", env = {...} }
      - [{ task = "fmt" }, { task = "lint" }]  (shorthand deps-only)
    """
    if isinstance(taskdef, str):
        return taskdef, [], None, {}
    if isinstance(taskdef, list):
        # shorthand deps-only
        return None, taskdef, None, {}
    if isinstance(taskdef, dict):
        cmd = taskdef.get("cmd")
        deps = taskdef.get("depends-on") or taskdef.get("depends_on") or []
        cwd = taskdef.get("cwd")
        env = taskdef.get("env") or {}
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError(f"Task cwd must be string: {taskdef}")
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise ValueError(f"Task env must be string dict: {taskdef}")
        return cmd, deps, cwd, env
    return None, [], None, {}


class TaskRunner:
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path.resolve()
        self.root = self.manifest_path.parent
        self.data = _toml_load(self.manifest_path)
        self.tasks = _extract_tasks(self.manifest_path, self.data)

    def list_tasks(self) -> List[str]:
        return sorted(self.tasks.keys())

    def run(self, argv: List[str]) -> int:
        if not argv:
            argv = ["help"]

        name, *rest = argv

        if name == "help":
            if self.tasks:
                print(f"Manifest: {self.manifest_path}")
                print("Tasks:")
                for k in self.list_tasks():
                    print(f"  {k}")
                print("\nRun: <image> <task> [args...]  OR  <image> <command> [args...]")
            else:
                print(f"Manifest: {self.manifest_path}")
                print("No tasks found.")
            return 0

        if name in self.tasks:
            return self._run_task(name, rest, call_stack=[])
        # not a task -> execute as command
        return self._exec_cmd([name, *rest], cwd=str(Path.cwd()), env_add={})

    def _run_task(self, name: str, args: List[str], call_stack: List[str],
                  cwd_override: Optional[str] = None,
                  env_override: Optional[Dict[str, str]] = None) -> int:
        if name in call_stack:
            cycle = " -> ".join([*call_stack, name])
            raise RuntimeError(f"Cycle detected in tasks: {cycle}")

        taskdef = self.tasks[name]
        cmd, deps, cwd, env = _task_def_to_spec(taskdef)

        # resolve working dir: override > task cwd > root
        wd = self.root
        if cwd is not None:
            wd = (self.root / cwd)
        if cwd_override is not None:
            wd = (self.root / cwd_override)

        # resolve env: task env merged with override
        env_add: Dict[str, str] = {}
        env_add.update(env)
        if env_override:
            env_add.update(env_override)

        # run dependencies first
        for dep in deps or []:
            dep_name, dep_args, dep_cwd, dep_env = _normalize_dep_entry(dep)
            rc = self._run_task(
                dep_name,
                dep_args,
                call_stack=[*call_stack, name],
                cwd_override=dep_cwd,
                env_override=dep_env,
            )
            if rc != 0:
                return rc

        # deps-only shorthand task
        if cmd is None and (isinstance(taskdef, list) or (isinstance(taskdef, dict) and not taskdef.get("cmd"))):
            return 0

        # execute command
        if isinstance(cmd, str):
            # append args to string command (pixi-like)
            full = cmd if not args else cmd + " " + " ".join(args)
            return self._exec_shell(full, cwd=str(wd), env_add=env_add)
        if isinstance(cmd, list):
            full_list = [*map(str, cmd), *map(str, args)]
            return self._exec_cmd(full_list, cwd=str(wd), env_add=env_add)

        raise RuntimeError(f"Unsupported task cmd type for {name}: {type(cmd)}")

    def _exec_shell(self, cmd: str, cwd: str, env_add: Dict[str, str]) -> int:
        env = os.environ.copy()
        env.update(env_add)
        p = subprocess.run(cmd, shell=True, cwd=cwd, env=env)
        return int(p.returncode)

    def _exec_cmd(self, cmd: List[str], cwd: str, env_add: Dict[str, str]) -> int:
        env = os.environ.copy()
        env.update(env_add)
        p = subprocess.run(cmd, cwd=cwd, env=env)
        return int(p.returncode)


def main() -> int:
    manifest_env = os.environ.get("PIXI_MANIFEST")
    if manifest_env:
        manifest = Path(manifest_env)
        if manifest.is_dir():
            mf = _find_manifest(manifest)
            if mf is None:
                raise SystemExit(f"Could not find pixi.toml or pyproject.toml under: {manifest}")
            manifest = mf
    else:
        mf = _find_manifest(Path.cwd())
        if mf is None:
            # common container default
            fallback = Path("/opt/app")
            mf = _find_manifest(fallback)
        if mf is None:
            raise SystemExit("Could not find pixi.toml or pyproject.toml (set PIXI_MANIFEST).")
        manifest = mf

    runner = TaskRunner(manifest)
    return runner.run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
