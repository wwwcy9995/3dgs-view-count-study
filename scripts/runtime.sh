#!/usr/bin/env bash
# Source this helper; it does not install or start training by itself.
PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA="${SPLAT_CONDA_EXE:-${CONDA_EXE:-$HOME/miniconda3/bin/conda}}"
CONDA_ROOT="$(dirname -- "$(dirname -- "$CONDA")")"
ENV_DIR="${SPLAT_ENV_DIR:-$CONDA_ROOT/envs/splat-course}"
UPSTREAM="${SPLAT_UPSTREAM_DIR:-$HOME/src/splat-course/nerfstudio}"
export PROJECT CONDA ENV_DIR UPSTREAM
splat_course_require_environment() {
  if [ ! -x "$ENV_DIR/bin/python" ]; then
    echo "Missing training environment: $ENV_DIR. Set SPLAT_ENV_DIR or run step 01." >&2
    return 1
  fi
  export PATH="$ENV_DIR/bin:$PATH"
}
