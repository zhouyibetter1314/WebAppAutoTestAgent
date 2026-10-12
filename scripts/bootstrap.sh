#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v uv >/dev/null && [[ ! -x .tools/bin/uv ]]; then
  curl -LsSf https://astral.sh/uv/0.13.0/install.sh | env UV_INSTALL_DIR="$PWD/.tools/bin" UV_NO_MODIFY_PATH=1 sh
fi
export PATH="$PWD/.tools/bin:$PATH"
export UV_CACHE_DIR="$PWD/.cache/uv"
if [[ "$(node -p 'process.versions.node.split(".")[0]')" != 24 ]]; then
  echo '请先安装 .node-version 中的 Node 24，再重新初始化。'; exit 1
fi
if ! command -v pnpm >/dev/null; then
  echo '请安装 pnpm 12.11.2：npm install --global pnpm@12.11.2'; exit 1
fi
uv sync --frozen --all-groups
git submodule update --init --recursive
uv run python scripts/check_targets.py
pnpm --dir frontend install --frozen-lockfile
uv run playwright install chromium
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
[[ -f .env ]] || cp .env.example .env
uv run waat doctor
