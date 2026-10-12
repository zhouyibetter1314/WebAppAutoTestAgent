import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .config import Settings
from .diagnostics import diagnose
from .model import Model, ModelError
from .runner import export_bundle
from .schemas import (
    TERMINAL,
    Application,
    ApplicationInput,
    Event,
    ImportScenarios,
    Run,
    RunRequest,
    Scenario,
    ScenarioInput,
    SettingsInfo,
)
from .service import Service


def create_app(
    settings: Settings | None = None, model_factory: Callable[[], Model] | None = None
) -> FastAPI:
    configuration = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        service = Service(configuration, model_factory)
        service.open()
        app.state.service = service
        try:
            yield
        finally:
            await service.close()

    api = FastAPI(title="WebAppAutoTestAgent", version="0.1.0", lifespan=lifespan)

    def service() -> Service:
        return api.state.service  # type: ignore[no-any-return]

    @api.exception_handler(KeyError)
    async def missing(_request: Request, _exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "记录不存在"})

    @api.exception_handler(ModelError)
    async def model_error(_request: Request, exc: ModelError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @api.middleware("http")
    async def local_origin(request: Request, call_next: Callable) -> object:
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            allowed = {
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            }
            if origin not in allowed:
                return JSONResponse(status_code=403, content={"detail": "只接受本机工作台请求"})
        return await call_next(request)

    @api.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/api/environment")
    def environment() -> dict[str, str]:
        return diagnose(configuration)

    @api.get("/api/settings", response_model=SettingsInfo)
    def settings_info() -> SettingsInfo:
        return SettingsInfo.model_validate(service().settings_info())

    @api.get("/api/applications", response_model=list[Application])
    def applications() -> list[Application]:
        return [Application.model_validate(v) for v in service().store.list("application")]

    @api.post("/api/applications", response_model=Application, status_code=201)
    def create_application(value: ApplicationInput) -> Application:
        return service().add_application(value)

    @api.put("/api/applications/{identifier}", response_model=Application)
    def update_application(identifier: str, value: ApplicationInput) -> Application:
        service().store.get("application", identifier)
        application = Application(id=identifier, **value.model_dump())
        service().store.save("application", application)
        return application

    @api.get("/api/scenarios", response_model=list[Scenario])
    def scenarios() -> list[Scenario]:
        return [Scenario.model_validate(v) for v in service().store.list("scenario")]

    @api.post("/api/scenarios", response_model=Scenario, status_code=201)
    def create_scenario(value: ScenarioInput) -> Scenario:
        return service().add_scenario(value)

    @api.put("/api/scenarios/{identifier}", response_model=Scenario)
    def update_scenario(identifier: str, value: ScenarioInput) -> Scenario:
        service().store.get("scenario", identifier)
        service().store.get("application", value.application_id)
        scenario = Scenario(id=identifier, **value.model_dump())
        service().store.save("scenario", scenario)
        return scenario

    @api.post("/api/scenarios/import", response_model=list[Scenario], status_code=201)
    def import_scenarios(value: ImportScenarios) -> list[Scenario]:
        for item in value.scenarios:
            service().store.get("application", item.application_id)
        return [service().add_scenario(item) for item in value.scenarios]

    @api.get("/api/runs", response_model=list[Run])
    def runs() -> list[Run]:
        return sorted(
            [Run.model_validate(v) for v in service().store.list("run")],
            key=lambda r: r.created_at,
            reverse=True,
        )

    @api.post("/api/runs", response_model=Run, status_code=202)
    async def create_run(value: RunRequest) -> Run:
        return service().submit(value)

    @api.get("/api/runs/{identifier}", response_model=Run)
    def get_run(identifier: str) -> Run:
        return service().store.run(identifier)

    @api.post("/api/runs/{identifier}/cancel", response_model=Run)
    async def cancel_run(identifier: str) -> Run:
        return service().cancel(identifier)

    @api.get("/api/runs/{identifier}/events", response_model=list[Event])
    def events(identifier: str, after: Annotated[int, Query(ge=0)] = 0) -> list[Event]:
        service().store.run(identifier)
        return service().store.events(identifier, after)

    @api.get("/api/runs/{identifier}/events/stream")
    async def stream(
        identifier: str,
        request: Request,
        after: Annotated[int, Query(ge=0)] = 0,
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> StreamingResponse:
        service().store.run(identifier)
        try:
            cursor = max(after, int(last_event_id or 0))
        except ValueError as exc:
            raise HTTPException(400, "无效的事件序号") from exc

        async def generate() -> AsyncIterator[str]:
            nonlocal cursor
            while not await request.is_disconnected():
                for item in service().store.events(identifier, cursor):
                    cursor = item.sequence
                    yield f"id: {cursor}\nevent: update\ndata: {item.model_dump_json()}\n\n"
                if service().store.run(identifier).status in TERMINAL:
                    yield "event: complete\ndata: {}\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @api.get("/api/runs/{identifier}/export")
    def export(identifier: str) -> FileResponse:
        run = service().store.run(identifier)
        if run.report is None:
            raise HTTPException(409, "报告尚未生成")
        path = export_bundle(service().store, run)
        return FileResponse(path, filename=f"waat-{identifier}.zip", media_type="application/zip")

    @api.get("/api/runs/{identifier}/artifacts/{filename}")
    def artifact(identifier: str, filename: str) -> FileResponse:
        run = service().store.run(identifier)
        allowed = {o.screenshot for o in run.observations} | {o.snapshot for o in run.observations}
        if run.report:
            allowed |= {"report.json", "report.md", "events.jsonl", "environment.json"}
            if run.report.trace:
                allowed.add(run.report.trace)
        if filename not in allowed:
            raise HTTPException(404, "文件不存在")
        path = service().store.root / "runs" / identifier / filename
        if not path.is_file():
            raise HTTPException(404, "文件不存在")
        return FileResponse(path)

    return api


def export_openapi() -> str:
    return json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n"
