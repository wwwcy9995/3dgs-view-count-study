#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/runtime.sh"
splat_course_require_environment
export PATH="$ENV_DIR/bin:$PATH"
export PYTHONNOUSERSITE=1
export TORCH_HOME="$PROJECT/.cache/torch"
export MAX_JOBS=2
export TORCH_CUDA_ARCH_LIST=8.6
mkdir -p "$PROJECT/records/setup"
exec > >(tee -a "$PROJECT/records/setup/verify-environment.log") 2>&1
cd "$PROJECT"
python scripts/verify_environment.py
python scripts/prepare_splits.py
python scripts/plot_camera_splits.py
if [ ! -s records/setup/splatfacto-help.txt ]; then bash scripts/check_cli.sh; fi
printf 'ENVIRONMENT_AND_SPLITS_VERIFIED\n'
