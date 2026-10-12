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
