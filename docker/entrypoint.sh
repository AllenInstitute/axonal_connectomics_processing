#!/usr/bin/env bash
set -euo pipefail

# Activates the unpacked env (sets PATH/CONDA_PREFIX + runs activate.d scripts)
# source /opt/pixi/activate.sh

exec python /usr/local/lib/pixi_task_runner.py "$@"
