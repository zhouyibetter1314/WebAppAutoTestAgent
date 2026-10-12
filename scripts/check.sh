#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.tools/bin:$PATH"
export UV_CACHE_DIR="$PWD/.cache/uv"
mode="${1:-all}"
if [[ "$mode" == format ]]; then
  uv run ruff check src tests scripts --fix
  uv run ruff format src tests scripts
  pnpm --dir frontend format
  exit
fi
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
pnpm --dir frontend typecheck
uv run pytest -q -m 'not browser and not live'
pnpm --dir frontend test
if [[ "$mode" != quick ]]; then
  pnpm --dir frontend lint
  pnpm --dir frontend format:check
  pnpm --dir frontend build
  uv run pytest -q -m 'browser and not live'
  uv run python scripts/check_api.py
fi
