#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/runtime.sh"
mkdir -p "$PROJECT/records/setup"
exec > >(tee -a "$PROJECT/records/setup/create-environment.log") 2>&1
date --iso-8601=seconds
if [ ! -x "$ENV_DIR/bin/python" ]; then
  "$CONDA" create --prefix "$ENV_DIR" --override-channels -c conda-forge python=3.10.22 pip -y
fi
"$ENV_DIR/bin/python" --version
"$ENV_DIR/bin/python" -m pip --version
printf 'ENVIRONMENT_READY\n'
