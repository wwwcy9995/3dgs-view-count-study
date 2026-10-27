#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/runtime.sh"
export PATH="$ENV_DIR/bin:$PATH"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_PROGRESS_BAR=off
export MAX_JOBS=2
export TORCH_CUDA_ARCH_LIST=8.6
export CC=gcc
export CXX=g++
export TORCH_HOME="$PROJECT/.cache/torch"
mkdir -p "$PROJECT/records/setup" "$(dirname "$UPSTREAM")"
exec > >(tee -a "$PROJECT/records/setup/install-training.log") 2>&1
cd "$PROJECT"
date --iso-8601=seconds
python -m pip install 'numpy==1.26.4' 'setuptools<81' wheel 'packaging<26'
python -m pip install 'torch==2.1.2+cu118' 'torchvision==0.16.2+cu118' \
  --index-url https://download.pytorch.org/whl/cu118
python -m pip install 'gsplat==1.4.0+pt21cu118' --no-deps \
  --index-url https://docs.gsplat.studio/whl/pt21cu118
if [ ! -d "$UPSTREAM/.git" ]; then
  git clone --depth 1 --branch v1.1.5 https://github.com/nerfstudio-project/nerfstudio.git "$UPSTREAM"
fi
if [ "$(git -C "$UPSTREAM" rev-parse HEAD)" != "6b60855003011b2ca23c2fe3f8e2ca6314c69924" ]; then
  echo "Upstream revision differs from the recorded experiment; use a clean v1.1.5 checkout." >&2
  exit 1
fi
git -C "$UPSTREAM" rev-parse HEAD > records/setup/nerfstudio-commit.txt
printf '%s\n' "$UPSTREAM" > records/setup/nerfstudio-source-path.txt
python -m pip install -c configs/constraints.txt -e "$UPSTREAM" \
  --index-url https://pypi.org/simple --prefer-binary --retries 8 --timeout 45 \
  --report records/setup/pip-install-report.json
python -m pip check
python -m pip freeze > records/setup/pip-freeze.txt
"$CONDA" list --prefix "$ENV_DIR" --explicit > records/setup/conda-explicit.txt
printf 'TRAINING_PACKAGES_READY\n'
