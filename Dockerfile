# syntax=docker/dockerfile:1.6
FROM ghcr.io/prefix-dev/pixi:latest AS builder

WORKDIR /opt/app

RUN apt-get update && apt-get install -y --no-install-recommends git make cmake g++ \
 && rm -rf /var/lib/apt/lists/*

# Copy manifest + lock first (adjust if you use pixi.toml instead)
COPY pyproject.toml pixi.lock ./

# Copy local editable deps BEFORE installing so pip/uv can install them
# (and so Docker caching only invalidates when submodules change)
COPY repos/ ./repos/

ARG PIXI_ENV=default

# # Build the environment strictly from lock
# RUN --mount=type=cache,target=/tmp/pixi-cache,sharing=locked \
#     PIXI_CACHE_DIR=/tmp/pixi-cache \
#     pixi install --locked -e "${PIXI_ENV}"
RUN --mount=type=cache,target=/tmp/pixi-cache,sharing=locked \
    --mount=type=bind,source=.git,target=/opt/app/.git,readonly \
    PIXI_CACHE_DIR=/tmp/pixi-cache \
    pixi install --locked -e "${PIXI_ENV}"

# Copy the rest of the repo (your non-submodule code, configs, etc.)
COPY . .

# --- runtime image ---
FROM ubuntu:jammy

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates bash git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/app /opt/app

ARG PIXI_ENV=default
ENV PIXI_ENV="${PIXI_ENV}" \
    PATH="/opt/app/.pixi/envs/${PIXI_ENV}/bin:${PATH}" \
    PYTHONNOUSERSITE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    XDG_CACHE_HOME=/tmp/.cache

WORKDIR /opt/app

# Optional: your task/command runner entrypoint (no pixi at runtime)
COPY docker/pixi_task_runner.py /usr/local/lib/pixi_task_runner.py
COPY docker/entrypoint.sh /usr/local/bin/inenv
RUN chmod +x /usr/local/bin/inenv

ENTRYPOINT ["/usr/local/bin/inenv"]
CMD ["help"]
