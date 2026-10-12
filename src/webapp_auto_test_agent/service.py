import asyncio
from collections.abc import Callable
from typing import Any

from filelock import FileLock, Timeout

from .browser import BrowserSession
from .config import Settings
from .model import DeepSeekModel, Model, ModelError
from .runner import Runner, write_report
from .schemas import (
    TERMINAL,
    Application,
    ApplicationInput,
    Report,
    Run,
    RunRequest,
    RunStatus,
    Scenario,
    ScenarioInput,
    Verdict,
    now,
)
from .storage import Store


class BusyError(RuntimeError):
    pass


class Service:
    def __init__(
        self,
        settings: Settings,
        model_factory: Callable[[], Model] | None = None,
        browser_factory: Callable[..., BrowserSession] = BrowserSession,
    ) -> None:
        self.settings = settings
        self.store = Store(settings)
        self.model_factory = model_factory or (lambda: DeepSeekModel(settings))
        self.custom_model = model_factory is not None
        self.browser_factory = browser_factory
        self.lock = FileLock(str(self.store.root / "runner.lock"))
        self.tasks: dict[str, asyncio.Task[Run]] = {}
        self.cancellations: dict[str, asyncio.Event] = {}
        self.gate = asyncio.Semaphore(1)

    def open(self) -> None:
        try:
            self.lock.acquire(timeout=0)
        except Timeout as exc:
            raise BusyError("已有后端或 CLI 正在使用这个数据目录，请连接该服务或先停止它") from exc
        for value in self.store.list("run"):
            run = Run.model_validate(value)
            if run.status not in TERMINAL:
                run.status, run.verdict = RunStatus.INTERRUPTED, Verdict.INCONCLUSIVE
                run.reason, run.finished_at = "上次服务退出，浏览器操作不会自动重放", now()
                run.report = Report(
                    run_id=run.id,
                    scenario=run.scenario,
                    application=run.application,
                    status=run.status,
                    verdict=run.verdict,
                    reason=run.reason,
                    checkpoints=run.checkpoints,
                    observations=run.observations,
                    resources=run.resources,
                    trace="trace.zip"
                    if (self.store.root / "runs" / run.id / "trace.zip").exists()
                    else None,
                    execution_mode="interrupted",
                    model={"required_version": self.settings.required_model},
                )
                self.store.save("run", run)
                self.store.emit(run.id, "interrupted", {"reason": run.reason})
                write_report(self.store, run)

    async def close(self) -> None:
        for identifier in list(self.tasks):
            self.cancel(identifier)
        if self.tasks:
            await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
        self.store.engine.dispose()
        self.lock.release()

    def add_application(self, value: ApplicationInput) -> Application:
        application = Application(**value.model_dump())
        self.store.save("application", application)
        return application

    def add_scenario(self, value: ScenarioInput) -> Scenario:
        self.store.get("application", value.application_id)
        scenario = Scenario(**value.model_dump())
        self.store.save("scenario", scenario)
        return scenario

    def submit(self, value: RunRequest) -> Run:
        if not self.custom_model and not self.settings.key_configured:
            raise ModelError("请先在本机 .env 配置 DEEPSEEK_API_KEY；真实验收尚未启用")
        scenario = Scenario.model_validate(self.store.get("scenario", value.scenario_id))
        application = Application.model_validate(
            self.store.get("application", scenario.application_id)
        )
        run = Run(scenario=scenario, application=application, max_steps=value.max_steps)
        self.store.save("run", run)
        self.store.emit(run.id, "queued", {})
        cancel = asyncio.Event()
        self.cancellations[run.id] = cancel
        task = asyncio.create_task(self._work(run, cancel))
        self.tasks[run.id] = task

        def completed(_task: asyncio.Task[Run]) -> None:
            self.tasks.pop(run.id, None)
            self.cancellations.pop(run.id, None)

        task.add_done_callback(completed)
        return run

    async def _work(self, run: Run, cancel: asyncio.Event) -> Run:
        try:
            async with self.gate:
                if cancel.is_set():
                    return self._cancel_queued(run)
                model = self.model_factory()
                runner = Runner(self.settings, self.store, run, model, cancel, self.browser_factory)
                return await runner.execute_run()
        except asyncio.CancelledError:
            return self._cancel_queued(run)
        except Exception as exc:
            run.status, run.verdict = RunStatus.ERROR, Verdict.INCONCLUSIVE
            run.reason, run.finished_at = str(exc)[:1000], now()
            run.report = Report(
                run_id=run.id,
                scenario=run.scenario,
                application=run.application,
                status=run.status,
                verdict=run.verdict,
                reason=run.reason,
                checkpoints=run.checkpoints,
                observations=run.observations,
                resources=run.resources,
                trace=None,
                execution_mode="not_started",
                model={},
            )
            self.store.save("run", run)
            self.store.emit(run.id, "error", {"reason": run.reason})
            write_report(self.store, run)
            return run
        finally:
            self.cancellations.pop(run.id, None)

    def _cancel_queued(self, run: Run) -> Run:
        saved = self.store.run(run.id)
        if saved.status in TERMINAL and saved.report:
            return saved
        run.status, run.verdict = RunStatus.CANCELLED, Verdict.INCONCLUSIVE
        run.reason, run.finished_at = "任务在启动前被取消", now()
        run.report = Report(
            run_id=run.id,
            scenario=run.scenario,
            application=run.application,
            status=run.status,
            verdict=run.verdict,
            reason=run.reason,
            checkpoints=[],
            observations=[],
            resources=run.resources,
            trace=None,
            execution_mode="not_started",
            model={},
        )
        self.store.save("run", run)
        self.store.emit(run.id, "cancelled", {})
        write_report(self.store, run)
        return run

    def cancel(self, identifier: str) -> Run:
        run = self.store.run(identifier)
        if identifier in self.cancellations and not self.cancellations[identifier].is_set():
            self.cancellations[identifier].set()
            if run.status == RunStatus.QUEUED:
                run = self._cancel_queued(run)
            task = self.tasks.get(identifier)
            if task:
                task.cancel()
        return run

    def settings_info(self) -> dict[str, Any]:
        return {
            "model_configured": self.settings.key_configured,
            "required_model": self.settings.required_model,
            "api_model": self.settings.api_model,
            "base_url": self.settings.model_base_url,
            "max_steps": 35,
            "headless": self.settings.headless,
            "execution_mode": "test-double" if self.custom_model else "real",
        }
