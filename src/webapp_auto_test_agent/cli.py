import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import httpx
import typer

from .config import Settings
from .runner import export_bundle
from .schemas import TERMINAL, RunRequest, ScenarioFile, ScenarioInput, Verdict
from .service import BusyError, Service
from .storage import Store

app = typer.Typer(help="WebAppAutoTestAgent：自主测试、环境诊断和报告", no_args_is_help=True)
targets_app = typer.Typer(help="本项目专用被测环境")
report_app = typer.Typer(help="Beamer 汇报")
app.add_typer(targets_app, name="targets")
app.add_typer(report_app, name="report")


def root() -> Path:
    return Path(__file__).resolve().parents[2]


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """启动本地 API（单进程，顺序运行任务）。"""
    import uvicorn

    uvicorn.run("webapp_auto_test_agent.api:create_app", factory=True, host=host, port=port)


@app.command()
def dev() -> None:
    """同时启动后端和 Vue 开发服务器。"""
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise typer.BadParameter("未找到 pnpm，请运行初始化脚本")
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "webapp_auto_test_agent", "serve"],
            start_new_session=os.name == "posix",
        ),
        subprocess.Popen(
            [pnpm, "--dir", str(root() / "frontend"), "dev"], start_new_session=os.name == "posix"
        ),
    ]
    typer.echo("工作台 http://127.0.0.1:5173 · API http://127.0.0.1:8000/docs")
    try:
        while all(p.poll() is None for p in processes):
            import time

            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()


@app.command()
def doctor() -> None:
    """检查环境，只报告密钥是否配置。"""
    from .diagnostics import diagnose

    typer.echo(json.dumps(diagnose(Settings()), ensure_ascii=False, indent=2))


async def run_files(files: list[ScenarioFile], max_steps: int, server: str | None) -> int:
    if server:
        async with httpx.AsyncClient(base_url=server.rstrip("/"), timeout=30) as client:
            exit_code = 0
            for file in files:
                response = await client.post(
                    "/api/applications", json=file.application.model_dump(mode="json")
                )
                response.raise_for_status()
                application_id = response.json()["id"]
                response = await client.post(
                    "/api/scenarios",
                    json={
                        "application_id": application_id,
                        "name": file.name,
                        "description": file.description,
                        "source": file.source,
                    },
                )
                response.raise_for_status()
                response = await client.post(
                    "/api/runs", json={"scenario_id": response.json()["id"], "max_steps": max_steps}
                )
                response.raise_for_status()
                identifier = response.json()["id"]
                while True:
                    response = await client.get(f"/api/runs/{identifier}")
                    response.raise_for_status()
                    result = response.json()
                    if result["status"] in TERMINAL:
                        typer.echo(json.dumps(result, ensure_ascii=False))
                        exit_code = max(
                            exit_code,
                            0
                            if result["verdict"] == "PASS"
                            else (1 if result["verdict"] == "FAIL" else 2),
                        )
                        break
                    await asyncio.sleep(0.5)
            return exit_code
    service = Service(Settings())
    service.open()
    try:
        exit_code = 0
        for file in files:
            application = service.add_application(file.application)
            scenario = service.add_scenario(
                ScenarioInput(
                    application_id=application.id,
                    name=file.name,
                    description=file.description,
                    source=file.source,
                )
            )
            run = service.submit(RunRequest(scenario_id=scenario.id, max_steps=max_steps))
            task = service.tasks[run.id]
            result = await task
            typer.echo(result.model_dump_json())
            if result.report:
                typer.echo(f"报告包：{export_bundle(service.store, result)}", err=True)
            exit_code = max(
                exit_code,
                0
                if result.verdict == Verdict.PASS
                else (1 if result.verdict == Verdict.FAIL else 2),
            )
        return exit_code
    finally:
        await service.close()


@app.command()
def run(
    file: Annotated[Path, typer.Argument(exists=True)],
    max_steps: int = 35,
    server: str | None = None,
) -> None:
    """执行一个 JSON 场景；--server 可提交到已启动的后端。"""
    execute_files([ScenarioFile.model_validate_json(file.read_text())], max_steps, server)


@app.command()
def batch(
    file: Annotated[Path, typer.Argument(exists=True)],
    max_steps: int = 35,
    server: str | None = None,
) -> None:
    """顺序执行 JSON 场景数组。退出码：0 全部 PASS，1 包含 FAIL，2 无法判定/错误。"""
    values = json.loads(file.read_text())
    if not isinstance(values, list) or not values:
        raise typer.BadParameter("批量文件必须是非空场景数组")
    execute_files([ScenarioFile.model_validate(v) for v in values], max_steps, server)


def execute_files(files: list[ScenarioFile], max_steps: int, server: str | None) -> None:
    if not 1 <= max_steps <= 35:
        raise typer.BadParameter("max-steps 必须在 1–35 之间")
    try:
        code = asyncio.run(run_files(files, max_steps, server))
    except (BusyError, RuntimeError, httpx.HTTPError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    raise typer.Exit(code)


@app.command("export")
def export_run(run_id: str) -> None:
    store = Store(Settings())
    typer.echo(str(export_bundle(store, store.run(run_id))))


def compose(arguments: list[str]) -> None:
    executable = shutil.which("docker")
    if not executable:
        raise typer.BadParameter("未安装 Docker，请参阅 docs/development.md")
    result = subprocess.run(
        [
            executable,
            "compose",
            "-f",
            str(root() / "infra/compose.yaml"),
            "--project-name",
            "waat-boards",
            *arguments,
        ],
        cwd=root(),
    )
    if result.returncode:
        raise typer.Exit(result.returncode)


@targets_app.command("up")
def targets_up() -> None:
    """构建并启动固定源码的 4gaBoards。"""
    compose(["up", "-d", "--build", "--wait"])


@targets_app.command("stop")
def targets_stop() -> None:
    compose(["stop"])


@targets_app.command("status")
def targets_status() -> None:
    compose(["ps"])


@targets_app.command("reset")
def targets_reset(yes: bool = False) -> None:
    """删除本项目的测试数据卷并重新初始化。"""
    if not yes:
        typer.confirm("重置 waat-boards 的全部测试数据？", abort=True)
    compose(["down", "--volumes"])
    compose(["up", "-d", "--wait"])


@report_app.command("build")
def report_build() -> None:
    result = subprocess.run(
        [
            "latexmk",
            "-xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-outdir=build",
            "main.tex",
        ],
        cwd=root() / "report",
    )
    raise typer.Exit(result.returncode)


@report_app.command("stats")
def report_stats() -> None:
    """导出真实运行统计；测试替身结果不会进入汇报。"""
    store = Store(Settings())
    runs = [
        r for r in store.list("run") if r.get("report") and r["report"]["execution_mode"] == "real"
    ]
    counts = {verdict: sum(r["verdict"] == verdict for r in runs) for verdict in Verdict}
    output = root() / "report/generated"
    output.mkdir(parents=True, exist_ok=True)
    (output / "runs.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2))
    (output / "stats.tex").write_text(
        "\\begin{tabular}{lr}\\hline\n结论 & 次数\\\\\\hline\n"
        + "\n".join(f"{key} & {value}\\\\" for key, value in counts.items())
        + "\n\\hline\\end{tabular}\n",
        encoding="utf-8",
    )
    typer.echo(f"已导出 {len(runs)} 次真实运行。课程评测通过率需标准答案，不能用 PASS 占比替代。")


if __name__ == "__main__":
    app()
