import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from .config import Settings


def diagnose(settings: Settings) -> dict[str, str]:
    result = {
        name: shutil.which(name) or "未安装"
        for name in ("uv", "node", "pnpm", "docker", "xelatex", "latexmk", "git")
    }
    local_uv = Path(__file__).resolve().parents[2] / ".tools/bin/uv"
    if local_uv.exists():
        result["uv"] = str(local_uv)
    result["python"] = sys.version.split()[0]
    result["model"] = (
        "已配置，连接待运行验证" if settings.key_configured else "未配置，真实验收未验证"
    )
    if shutil.which("docker"):
        for name, command in [
            ("docker_daemon", ["docker", "info"]),
            ("docker_compose", ["docker", "compose", "version"]),
        ]:
            try:
                result[name] = (
                    "可用"
                    if subprocess.run(command, capture_output=True, timeout=5).returncode == 0
                    else "不可用"
                )
            except (OSError, subprocess.TimeoutExpired):
                result[name] = "不可用或检查超时"
    with sync_playwright() as playwright:
        path = Path(settings.browser_executable or playwright.chromium.executable_path)
        result["browser"] = str(path) if path.exists() else "未安装 Chromium"
    return result
