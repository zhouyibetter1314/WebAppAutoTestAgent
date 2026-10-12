"""Only launched by the offline UI test suite. No test-model switch in production API."""

import functools
import http.server
import os
import sys
import tempfile
import threading
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.fakes import FakeModel  # noqa: E402
from webapp_auto_test_agent.api import create_app  # noqa: E402
from webapp_auto_test_agent.config import Settings  # noqa: E402

with tempfile.TemporaryDirectory(prefix="waat-e2e-") as temp:
    root = Path(temp)
    (root / "index.html").write_text("""<!doctype html><title>Fixture</title><button
    onclick="document.querySelector('main').textContent='Course Test created'">Create</button>
    <main>No projects</main>""")
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 3017), functools.partial(http.server.SimpleHTTPRequestHandler, directory=temp)
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings = Settings(
        _env_file=None,
        data_dir=root / "data",
        DEEPSEEK_API_KEY="",
        browser_executable=os.getenv("WAAT_BROWSER_EXECUTABLE"),
    )
    try:
        uvicorn.run(create_app(settings, FakeModel), host="127.0.0.1", port=8000)
    finally:
        server.shutdown()
        server.server_close()
