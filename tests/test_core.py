import asyncio
import zipfile

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeout
from pydantic import HttpUrl, ValidationError

from webapp_auto_test_agent.browser import BrowserSession, StepLimit
from webapp_auto_test_agent.runner import export_bundle
from webapp_auto_test_agent.schemas import (
    Application,
    ApplicationInput,
    Click,
    LocatorSpec,
    Navigate,
    RunRequest,
    RunStatus,
    ScenarioInput,
    Verdict,
)
from webapp_auto_test_agent.service import BusyError, Service

from .fakes import FakeModel


def scenario(service, url):
    app = service.add_application(ApplicationInput(name="Fixture", base_url=HttpUrl(url)))
    return service.add_scenario(
        ScenarioInput(
            application_id=app.id,
            name="Create project",
            description="Create Course Test and check the result",
            source="test fixture",
        )
    )


@pytest.mark.browser
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [("satisfied", Verdict.PASS), ("violated", Verdict.FAIL), ("pending", Verdict.INCONCLUSIVE)],
)
async def test_real_browser_report(settings, page_server, outcome, expected):
    service = Service(settings, lambda: FakeModel(outcome))
    service.open()
    try:
        item = scenario(service, page_server)
        run = service.submit(RunRequest(scenario_id=item.id, max_steps=3))
        result = await service.tasks[run.id]
        assert result.verdict == expected
        assert result.report.trace == "trace.zip"
        assert result.report.execution_mode == "test-double"
        assert result.resources.browser_steps <= 3
        bundle = export_bundle(service.store, result)
        with zipfile.ZipFile(bundle) as z:
            assert {"report.json", "report.md", "trace.zip", "events.jsonl"} <= set(z.namelist())
        assert service.store.run(run.id).verdict == expected
        events = service.store.events(run.id)
        cursor = events[2].sequence
        assert all(e.sequence > cursor for e in service.store.events(run.id, cursor))
    finally:
        await service.close()


@pytest.mark.browser
async def test_operation_36_rejected_and_failed_attempts_count(settings, page_server, tmp_path):
    browser = BrowserSession(
        settings, Application(name="test", base_url=HttpUrl(page_server)), tmp_path, 35
    )
    await browser.start()
    try:
        await browser.execute(Navigate(kind="navigate", url=HttpUrl(page_server)))
        missing = Click(kind="click", target=LocatorSpec(by="text", value="missing"))
        for _ in range(34):
            with pytest.raises(PlaywrightTimeout):
                await browser.execute(missing)
        assert browser.steps == 35
        with pytest.raises(StepLimit):
            await browser.execute(missing)
        assert browser.steps == 35
        assert (await browser.observe()).screenshot
    finally:
        await browser.close()
    assert (tmp_path / "trace.zip").exists()


@pytest.mark.browser
@pytest.mark.parametrize("mode", ["bad_locator", "invalid_evidence"])
async def test_no_false_failure_or_invented_pass(settings, page_server, mode):
    service = Service(settings, lambda: FakeModel(**{mode: True}))
    service.open()
    try:
        run = service.submit(RunRequest(scenario_id=scenario(service, page_server).id, max_steps=4))
        result = await service.tasks[run.id]
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.resources.browser_steps == 4
        assert result.report
    finally:
        await service.close()


@pytest.mark.browser
async def test_cancel_preserves_evidence(settings, page_server):
    model = FakeModel(delay=10)
    service = Service(settings, lambda: model)
    service.open()
    try:
        run = service.submit(RunRequest(scenario_id=scenario(service, page_server).id))
        task = service.tasks[run.id]
        for _ in range(100):
            if service.store.run(run.id).resources.browser_steps:
                break
            await asyncio.sleep(0.05)
        service.cancel(run.id)
        service.cancel(run.id)
        result = await task
        assert result.status == "cancelled"
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.report and result.report.trace and model.closed
    finally:
        await service.close()


async def test_immediate_cancel_and_restart(settings):
    service = Service(settings, FakeModel)
    service.open()
    item = scenario(service, "http://localhost:3000")
    run = service.submit(RunRequest(scenario_id=item.id))
    service.cancel(run.id)
    assert service.store.run(run.id).status == "cancelled"
    await service.close()
    second = Service(settings, FakeModel)
    second.open()
    run.status = RunStatus.RUNNING
    second.store.save("run", run)
    await second.close()
    third = Service(settings, FakeModel)
    third.open()
    assert third.store.run(run.id).status == "interrupted"
    assert third.store.run(run.id).report
    await third.close()


async def test_exclusive_runner_lock(settings):
    first, second = Service(settings, FakeModel), Service(settings, FakeModel)
    first.open()
    with pytest.raises(BusyError):
        second.open()
    await first.close()
    second.store.engine.dispose()


def test_max_budget_validation():
    with pytest.raises(ValidationError):
        RunRequest(scenario_id="x", max_steps=36)


async def test_browser_start_failure_has_report(settings):
    class BrokenBrowser(BrowserSession):
        async def start(self):
            raise RuntimeError("fixture browser crash")

    service = Service(settings, FakeModel, BrokenBrowser)
    service.open()
    try:
        run = service.submit(RunRequest(scenario_id=scenario(service, "http://localhost:3000").id))
        result = await service.tasks[run.id]
        assert result.status == "error"
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.report and result.report.trace is None
        assert "fixture browser crash" in result.reason
    finally:
        await service.close()


@pytest.mark.browser
async def test_overall_timeout_closes_resources(settings, page_server):
    settings.run_timeout_seconds = 1
    model = FakeModel(delay=5)
    service = Service(settings, lambda: model)
    service.open()
    try:
        run = service.submit(RunRequest(scenario_id=scenario(service, page_server).id))
        result = await service.tasks[run.id]
        assert result.status == "error"
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.reason == "整体运行超时"
        assert result.report and model.closed
    finally:
        await service.close()


@pytest.mark.browser
async def test_observation_disambiguates_unlabelled_inputs_without_values(
    settings, tmp_path, monkeypatch
):
    import json

    monkeypatch.setenv("FIXTURE_PASSWORD", "fixture-private-password")
    application = Application(
        name="fixture", base_url=HttpUrl("http://localhost"), password_env="FIXTURE_PASSWORD"
    )
    browser = BrowserSession(settings, application, tmp_path, 35)
    await browser.start()
    try:
        await browser.page.set_content("""<title>Login</title><input name="username">
          <input name="password" type="password" value="fixture-private-password">
          <button>Login</button>""")
        observation = await browser.observe()
        selectors = {control["selector"] for control in observation.controls}
        assert 'input[name="username"]' in selectors
        assert 'input[name="password"]' in selectors
        assert "fixture-private-password" not in json.dumps(observation.controls)
        assert all("value" not in control for control in observation.controls)
    finally:
        await browser.close()


@pytest.mark.parametrize("omit_assessment", [False, True])
async def test_sidebar_quote_cannot_pass_dashboard_without_supported_audit(
    settings, omit_assessment
):
    from webapp_auto_test_agent.runner import Runner, determine_verdict
    from webapp_auto_test_agent.schemas import Checkpoint, Observation, Run

    class RejectScopeModel(FakeModel):
        async def ask(self, phase, payload, schema):
            self.resources.model_requests += 1
            if phase == "verify":
                return schema.model_validate(
                    {
                        "checks": [
                            {
                                "id": "dashboard",
                                "status": "satisfied",
                                "actual": "Sidebar shown; dashboard assumed.",
                                "evidence_ids": ["project-page"],
                                "quote": "Course Test",
                            }
                        ]
                    }
                )
            assert phase == "audit_evidence"
            assert payload["candidate_checks"][0]["observations"][0]["url"].endswith("/projects/1")
            return schema.model_validate(
                {
                    "checks": []
                    if omit_assessment
                    else [
                        {
                            "id": "dashboard",
                            "supported": False,
                            "reason": "Dashboard not observed after creation.",
                        }
                    ]
                }
            )

    service = Service(settings, FakeModel)
    service.open()
    try:
        item = scenario(service, "http://localhost:3000")
        application = Application.model_validate(
            service.store.get("application", item.application_id)
        )
        run = Run(
            scenario=item,
            application=application,
            checkpoints=[Checkpoint(id="dashboard", expected="Project appears on dashboard")],
            observations=[
                Observation(
                    id="project-page",
                    url="http://localhost:3000/projects/1",
                    title="Course Test",
                    aria='- link "Course Test"',
                    screenshot="e.png",
                    snapshot="e.json",
                )
            ],
        )
        runner = Runner(settings, service.store, run, RejectScopeModel(), asyncio.Event())
        runner.history = [{}, {}]
        state = await runner.verify({})
        assert run.checkpoints[0].status == "pending"
        assert determine_verdict(run.checkpoints) == Verdict.INCONCLUSIVE
        assert state["verification_feedback"][0]["checkpoint"] == "dashboard"
        assert any(e.kind == "verification_rejected" for e in service.store.events(run.id))
    finally:
        await service.close()


@pytest.mark.browser
async def test_finish_request_reverifies_rejected_quote(settings, page_server):
    class FinishAfterCreate(FakeModel):
        async def ask(self, phase, payload, schema):
            if phase == "next_action" and len(payload["recent_actions"]) >= 2:
                return schema.model_validate({"reason": "Creation looks done", "finish": True})
            result = await super().ask(phase, payload, schema)
            if phase == "verify" and not payload.get("final_verification"):
                result.checks[0].quote = "not an exact quote"
            return result

    service = Service(settings, FinishAfterCreate)
    service.open()
    try:
        run = service.submit(RunRequest(scenario_id=scenario(service, page_server).id))
        result = await service.tasks[run.id]
        assert result.verdict == Verdict.PASS
        assert result.resources.browser_steps == 2
        events = service.store.events(run.id)
        assert any(e.kind == "verification_rejected" for e in events)
        assert any(e.kind == "final_verification" for e in events)
        assert any(e.kind == "evidence_audit" for e in events)
    finally:
        await service.close()


@pytest.mark.browser
async def test_premature_finish_does_not_manufacture_pass(settings, page_server):
    class FinishImmediately(FakeModel):
        async def ask(self, phase, payload, schema):
            if phase == "next_action":
                return schema.model_validate({"reason": "Assume done", "finish": True})
            return await super().ask(phase, payload, schema)

    service = Service(settings, FinishImmediately)
    service.open()
    try:
        run = service.submit(RunRequest(scenario_id=scenario(service, page_server).id))
        result = await service.tasks[run.id]
        assert result.verdict == Verdict.INCONCLUSIVE
        assert result.resources.browser_steps == 1
        assert sum(e.kind == "final_verification" for e in service.store.events(run.id)) == 2
    finally:
        await service.close()


@pytest.mark.browser
async def test_observation_retries_when_url_and_title_change(
    settings, page_server, tmp_path, monkeypatch
):
    browser = BrowserSession(
        settings, Application(name="fixture", base_url=HttpUrl(page_server)), tmp_path, 35
    )
    await browser.start()
    try:
        await browser.execute(Navigate(kind="navigate", url=HttpUrl(page_server)))
        original_title = browser.page.title
        calls = 0

        async def transitioning_title():
            nonlocal calls
            calls += 1
            title = await original_title()
            if calls == 1:
                await browser.page.evaluate(
                    "history.replaceState(null, '', '/changed'); document.title = 'New page'"
                )
            return title

        monkeypatch.setattr(browser.page, "title", transitioning_title)
        observation = await browser.observe()
        assert observation.url.endswith("/changed")
        assert observation.title == "New page"
        assert calls >= 4
        assert browser.steps == 1
        assert len(list(tmp_path.glob("*.png"))) == 1
    finally:
        await browser.close()
