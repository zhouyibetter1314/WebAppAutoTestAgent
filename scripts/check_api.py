"""Compare semantic schemas without coupling checks to JSON whitespace."""

import json
from pathlib import Path

from webapp_auto_test_agent.api import export_openapi

if json.loads(Path("frontend/openapi.json").read_text()) != json.loads(export_openapi()):
    raise SystemExit(
        "OpenAPI 已变化：运行 python scripts/export_openapi.py 和 pnpm --dir frontend generate:api"
    )
