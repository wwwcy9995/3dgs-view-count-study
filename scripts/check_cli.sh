#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/runtime.sh"
splat_course_require_environment
export PATH="$ENV_DIR/bin:$PATH"
export TORCH_COMPILE_DISABLE=1
cd "$PROJECT"
ns-train splatfacto --help > records/setup/splatfacto-help.txt
ns-train splatfacto blender-data --help > records/setup/blender-data-help.txt
ns-export gaussian-splat --help > records/setup/export-help.txt
printf 'TRAIN_EVAL_EXPORT_CLI_CHECKED\n'
