import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from webapp_auto_test_agent.api import create_app
from webapp_auto_test_agent.model import DeepSeekModel, ModelError
from webapp_auto_test_agent.schemas import Decision

from .fakes import FakeModel


def test_missing_key_and_origin(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/settings").json()["model_configured"] is False
        assert client.post("/api/runs", json={"scenario_id": "x"}).status_code == 409
        assert (
            client.post(
                "/api/applications", json={}, headers={"Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert client.get("/api/runs/missing").status_code == 404


@pytest.mark.browser
def test_api_sse_report_reload(settings, page_server):
    with TestClient(create_app(settings, FakeModel)) as client:
        app = client.post(
            "/api/applications", json={"name": "fixture", "base_url": page_server}
        ).json()
        scenario = client.post(
            "/api/scenarios",
            json={
                "application_id": app["id"],
                "name": "Create",
                "description": "Create Course Test",
            },
        ).json()
        run = client.post("/api/runs", json={"scenario_id": scenario["id"]}).json()
        url = f"/api/runs/{run['id']}"
        stream = client.get(url + "/events/stream")
        assert "event: complete" in stream.text
        result = client.get(url).json()
        assert result["verdict"] == "PASS"
        events = client.get(url + "/events").json()
        tail = client.get(
            url + "/events/stream", headers={"Last-Event-ID": str(events[-1]["sequence"])}
        )
        assert "event: update" not in tail.text
        assert client.get(url + "/export").status_code == 200
        assert client.get(url + "/artifacts/runner.lock").status_code == 404
        assert (
            client.get(url + "/artifacts/" + result["observations"][0]["screenshot"]).status_code
            == 200
        )
    with TestClient(create_app(settings, FakeModel)) as client:
        assert client.get(url).json()["verdict"] == "PASS"


@pytest.mark.parametrize("failure", ["timeout", "invalid"])
async def test_model_bounded_retries(settings, failure):
    settings.api_key = SecretStr("fixture-key")
    model = DeepSeekModel(settings)
    await model.client.aclose()

    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(
            200, json={"model": "fake", "choices": [{"message": {"content": "{}"}}]}
        )

    model.client = httpx.AsyncClient(
        base_url="https://test/", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ModelError):
        await model.ask("next_action", {}, Decision)
    assert model.resources.model_requests == 3
    await model.close()


async def test_model_repairs_action_wait_conflict_with_validation_feedback(settings):
    import json

    settings.api_key = SecretStr("fixture-key")
    model = DeepSeekModel(settings)
    await model.client.aclose()
    requests = []
    action = {
        "kind": "fill",
        "target": {"by": "css", "value": 'input[name="username"]'},
        "value": "{{username}}",
    }

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        result = {"reason": "Login", "action": action, "wait_ms": 300 if len(requests) == 1 else 0}
        return httpx.Response(
            200,
            json={
                "model": "fake",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "choices": [{"message": {"content": json.dumps(result)}}],
            },
        )

    model.client = httpx.AsyncClient(
        base_url="https://test/", transport=httpx.MockTransport(handler)
    )
    try:
        decision = await model.ask("next_action", {"original_scenario": "Create project"}, Decision)
        assert decision.action.kind == "fill"
        assert decision.wait_ms == 0
        assert len(requests) == 2
        correction = json.loads(requests[1]["messages"][-1]["content"])
        assert correction["validation_errors"][0]["field"] == "decision"
        assert "exactly one" in correction["validation_errors"][0]["message"]
        assert "input" not in model.calls[0]["validation_errors"][0]
        assert model.calls[0]["error"] == "ValidationError"
        assert model.resources.model_requests == 2
    finally:
        await model.close()
