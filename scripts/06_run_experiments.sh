#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/runtime.sh"
splat_course_require_environment
export PATH="$ENV_DIR/bin:$PATH"
export TORCH_HOME="$PROJECT/.cache/torch"
export TORCH_COMPILE_DISABLE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
export MAX_JOBS=2 TORCH_CUDA_ARCH_LIST=8.6
cd "$PROJECT"
python -u scripts/run_experiments.py "$@"
