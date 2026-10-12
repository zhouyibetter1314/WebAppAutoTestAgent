import functools
import http.server
import threading
from pathlib import Path

import pytest

from webapp_auto_test_agent.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        browser_executable="/usr/bin/google-chrome"
        if Path("/usr/bin/google-chrome").exists()
        else None,
        action_timeout_ms=250,
        DEEPSEEK_API_KEY="",
    )


@pytest.fixture
def page_server(tmp_path):
    (tmp_path / "index.html").write_text("""<!doctype html><title>Test board</title>
    <button
    onclick="document.querySelector('main').textContent='Course Test created'">Create</button>
    <main>No projects</main>""")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()
