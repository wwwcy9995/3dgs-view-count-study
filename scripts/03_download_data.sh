#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/runtime.sh"
splat_course_require_environment
mkdir -p "$PROJECT/records/setup"
exec > >(tee -a "$PROJECT/records/setup/download-data.log") 2>&1
date --iso-8601=seconds
"$ENV_DIR/bin/python" -u "$PROJECT/scripts/download_lego.py"
