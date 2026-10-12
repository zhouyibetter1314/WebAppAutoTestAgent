import asyncio
import os
from pathlib import Path

import pytest

from webapp_auto_test_agent.cli import run_files
from webapp_auto_test_agent.config import Settings
from webapp_auto_test_agent.schemas import ScenarioFile


@pytest.mark.live
async def test_deepseek_4gaboards():
    if os.getenv("WAAT_LIVE") != "1" or not Settings().key_configured:
        pytest.skip("未验证：需显式 WAAT_LIVE=1、DeepSeek 密钥及已启动的 4gaBoards")
    file = ScenarioFile.model_validate_json(
        await asyncio.to_thread(Path("examples/create_project.json").read_text)
    )
    assert await run_files([file], 35, None) == 0
