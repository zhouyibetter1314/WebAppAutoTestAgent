from pathlib import Path

from webapp_auto_test_agent.api import export_openapi

Path("frontend/openapi.json").write_text(export_openapi(), encoding="utf-8")
