#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/runtime.sh"
mkdir -p "$PROJECT/records/setup"
exec > >(tee -a "$PROJECT/records/setup/system-dependencies.log") 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends build-essential libgl1 libglib2.0-0 libglu1-mesa
gcc --version | head -n 1
printf 'SYSTEM_BUILD_TOOLS_READY\n'
