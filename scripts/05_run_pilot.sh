#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/runtime.sh"
splat_course_require_environment
export PATH="$ENV_DIR/bin:$PATH"
export TORCH_HOME="$PROJECT/.cache/torch"
export TORCH_COMPILE_DISABLE=1
export MAX_JOBS=2
export TORCH_CUDA_ARCH_LIST=8.6
cd "$PROJECT"
python -u scripts/run_pilot.py --steps 1000
python scripts/summarize_pilot.py
