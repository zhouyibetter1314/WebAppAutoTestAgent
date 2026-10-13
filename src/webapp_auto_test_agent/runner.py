import asyncio
import json
import platform
import time
import zipfile
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .browser import BrowserSession
from .config import Settings
from .model import Model
from .schemas import (
    Checkpoint,
    Decision,
    EvidenceAudit,
    Navigate,
    Plan,
    Report,
    Run,
    RunStatus,
    ScenarioSpec,
    Verdict,
    Verification,
    now,
)
from .storage import Store


class GraphState(TypedDict, total=False):
    specification: dict[str, Any]
    plan: dict[str, Any]
    decision: dict[str, Any]
    last_error: str
    recovery_attempts: int
    rounds: int
    stop: bool
    reason: str
    verification_feedback: list[dict[str, str]]
    final_verification: bool
    finish_attempts: int


def determine_verdict(checks: list[Checkpoint], reliable: bool = True) -> Verdict:
    if not reliable:
        return Verdict.INCONCLUSIVE
    if any(c.status == "violated" and c.evidence_ids for c in checks):
        return Verdict.FAIL
    if checks and all(c.status == "satisfied" and c.evidence_ids for c in checks):
        return Verdict.PASS
    return Verdict.INCONCLUSIVE


class Runner:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        run: Run,
        model: Model,
        cancel: asyncio.Event,
        browser_factory: Callable[..., BrowserSession] = BrowserSession,
    ) -> None:
        self.settings, self.store, self.run, self.model, self.cancel = (
            settings,
            store,
            run,
            model,
            cancel,
        )
        self.directory = store.root / "runs" / run.id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.browser = browser_factory(settings, run.application, self.directory, run.max_steps)
        self.history: list[dict[str, Any]] = []
        self.started = time.monotonic()

    def save(self, kind: str, data: dict[str, Any]) -> None:
        self.run.resources = self.model.resources.model_copy(deep=True)
        self.run.resources.browser_steps = self.browser.steps
        self.run.resources.elapsed_seconds = round(time.monotonic() - self.started, 3)
        self.store.save("run", self.run)
        self.store.emit(self.run.id, kind, data)

    def guard(self) -> None:
        if self.cancel.is_set():
            raise asyncio.CancelledError

    def payload(self, state: GraphState) -> dict[str, Any]:
        return {
            "original_scenario": self.run.scenario.description,
            "specification": state.get("specification"),
            "plan": state.get("plan"),
            "checkpoints": [c.model_dump() for c in self.run.checkpoints],
            "observations": [o.model_dump() for o in self.run.observations[-3:]],
            "baseline": self.run.observations[0].model_dump() if self.run.observations else None,
            "recent_actions": self.history[-8:],
            "steps_remaining": self.run.max_steps - self.browser.steps,
            "last_error": state.get("last_error", ""),
            "verification_feedback": state.get("verification_feedback", []),
            "final_verification": state.get("final_verification", False),
            "latest_observation": self.run.observations[-1].model_dump()
            if self.run.observations
            else None,
            "credential_placeholders_available": {
                k: bool(v) for k, v in self.browser.secrets.items()
            },
        }

    async def parse(self, state: GraphState) -> GraphState:
        self.guard()
        spec = await self.model.ask("parse_scenario", self.payload(state), ScenarioSpec)
        self.run.checkpoints = spec.checkpoints
        self.save("parsed", {"specification": spec.model_dump()})
        return {"specification": spec.model_dump(), "rounds": 0, "recovery_attempts": 0}

    async def plan(self, state: GraphState) -> GraphState:
        self.guard()
        plan = await self.model.ask("plan", self.payload(state), Plan)
        self.save("planned", plan.model_dump())
        return {"plan": plan.model_dump()}

    async def observe(self, state: GraphState) -> GraphState:
        self.guard()
        observation = await self.browser.observe()
        self.run.observations.append(observation)
        self.save("observation", observation.model_dump())
        (self.directory / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {}

    async def decide(self, state: GraphState) -> GraphState:
        self.guard()
        rounds = state.get("rounds", 0) + 1
        if self.browser.steps >= self.run.max_steps:
            return {"stop": True, "reason": "已达到浏览器操作上限，已完成最后观察与验证"}
        if rounds > self.run.max_steps * 2 + 10:
            return {"stop": True, "reason": "观察/等待轮次达到上限"}
        decision = await self.model.ask("next_action", self.payload(state), Decision)
        self.save("decision", decision.model_dump(mode="json"))
        return {
            "decision": decision.model_dump(mode="json"),
            "rounds": rounds,
            "stop": decision.finish,
            "reason": decision.reason if decision.finish else "",
        }

    async def perform(self, action: Any) -> str:
        self.guard()
        error = ""
        try:
            await self.browser.execute(action)
        except Exception as exc:
            error = self.browser.redact(str(exc))[:1200]
        entry = {
            "step": self.browser.steps,
            "action": action.model_dump(mode="json"),
            "error": error,
            "created_at": now(),
        }
        # Store only placeholders for credentials, including in exception messages.
        entry = json.loads(self.browser.redact(json.dumps(entry, ensure_ascii=False)))
        self.history.append(entry)
        self.save("action", entry)
        return error

    async def execute(self, state: GraphState) -> GraphState:
        decision = Decision.model_validate(state["decision"])
        if decision.wait_ms:
            await asyncio.sleep(decision.wait_ms / 1000)
            return {"last_error": ""}
        assert decision.action is not None
        error = await self.perform(decision.action)
        return {
            "last_error": error,
            "recovery_attempts": state.get("recovery_attempts", 0) if error else 0,
        }

    async def verify(self, state: GraphState) -> GraphState:
        self.guard()
        # Failed execution is handled by recovery, not misclassified as an application defect.
        if state.get("last_error") or (
            len(self.history) <= 1 and not state.get("final_verification")
        ):
            return {}
        result = await self.model.ask("verify", self.payload(state), Verification)
        observations = {o.id: o for o in self.run.observations}
        checks = {c.id: c for c in self.run.checkpoints}
        accepted: list[dict[str, Any]] = []
        feedback: list[dict[str, str]] = []
        candidates = []
        for update in result.checks:
            check = checks.get(update.id)
            if check is None:
                continue  # A verifier cannot invent new acceptance criteria.
            if update.status == "pending":
                check.status, check.actual, check.evidence_ids = (
                    update.status,
                    update.actual,
                    update.evidence_ids,
                )
                accepted.append(update.model_dump())
                continue
            valid_ids = bool(update.evidence_ids) and all(
                identifier in observations for identifier in update.evidence_ids
            )
            quoted = bool(update.quote.strip()) and any(
                update.quote in observations[identifier].aria
                for identifier in update.evidence_ids
                if identifier in observations
            )
            if not valid_ids or not quoted or not update.actual.strip():
                if not valid_ids:
                    reason = "引用了不存在的观察编号，请使用提供的 evidence IDs"
                elif not quoted:
                    reason = "引文不匹配，请从最新 ARIA 逐字复制一段连续原文，不要拼接或添加省略号"
                else:
                    reason = "缺少实际观察描述"
                feedback.append({"checkpoint": update.id, "reason": reason})
                continue
            candidates.append(update)
        if candidates:
            audit = await self.model.ask(
                "audit_evidence",
                {
                    "original_scenario": self.run.scenario.description,
                    "baseline": self.run.observations[0].model_dump(),
                    "recent_actions": self.history[-8:],
                    "candidate_checks": [
                        {
                            "checkpoint": checks[update.id].model_dump(),
                            "proposed": update.model_dump(),
                            "observations": [
                                observations[identifier].model_dump()
                                for identifier in update.evidence_ids
                            ],
                        }
                        for update in candidates
                    ],
                },
                EvidenceAudit,
            )
            self.save("evidence_audit", audit.model_dump())
            support = {item.id: item for item in audit.checks}
            for update in candidates:
                assessment = support.get(update.id)
                if assessment is None or not assessment.supported:
                    reason = assessment.reason if assessment else "证据审查未覆盖该检查点"
                    feedback.append({"checkpoint": update.id, "reason": reason})
                    check = checks[update.id]
                    if check.status == "pending":
                        check.actual = "证据仍不足：" + reason
                    continue
                check = checks[update.id]
                check.status, check.actual, check.evidence_ids = (
                    update.status,
                    update.actual,
                    update.evidence_ids,
                )
                accepted.append(update.model_dump())
        for item in feedback:
            self.save("verification_rejected", item)
        self.save("verification", {"checks": accepted})
        verdict = determine_verdict(self.run.checkpoints)
        if verdict != Verdict.INCONCLUSIVE:
            return {
                "stop": True,
                "reason": "全部检查点已验证"
                if verdict == Verdict.PASS
                else "已观察到与场景要求不一致的行为",
            }
        return {"verification_feedback": feedback}

    async def finalize(self, state: GraphState) -> GraphState:
        self.guard()
        attempts = state.get("finish_attempts", 0) + 1
        self.save("final_verification", {"attempt": attempts})
        # Finishing is an actor request, never a substitute for independent verification.
        await self.observe(state)
        result = await self.verify({**state, "final_verification": True})
        if determine_verdict(self.run.checkpoints) != Verdict.INCONCLUSIVE and not state.get(
            "last_error"
        ):
            return {**result, "stop": True, "finish_attempts": attempts}
        if (
            attempts >= 2
            or self.browser.steps >= self.run.max_steps
            or state.get("rounds", 0) > self.run.max_steps * 2 + 10
            or state.get("last_error")
        ):
            return {
                **result,
                "stop": True,
                "finish_attempts": attempts,
                "reason": "结束前复核仍有检查点缺少有效证据",
            }
        feedback = result.get("verification_feedback", [])
        if not feedback:
            feedback = [
                {"checkpoint": check.id, "reason": "该检查点未验证，请继续收集直接证据"}
                for check in self.run.checkpoints
                if check.status == "pending"
            ]
        return {
            **result,
            "stop": False,
            "reason": "",
            "finish_attempts": attempts,
            "final_verification": False,
            "verification_feedback": feedback,
        }

    async def recover(self, state: GraphState) -> GraphState:
        self.guard()
        attempts = state.get("recovery_attempts", 0) + 1
        self.save("recovery", {"attempt": attempts, "error": state.get("last_error", "")})
        if (
            attempts > self.settings.max_recovery_attempts
            or self.browser.steps >= self.run.max_steps
        ):
            return {"stop": True, "reason": "执行恢复失败，未能完成可靠验证"}
        # Feed the fresh observation and error back to the planner/actor; never replay blindly.
        return {"recovery_attempts": attempts}

    def graph(self) -> Any:
        graph = StateGraph(GraphState)
        for name in (
            "parse",
            "plan",
            "observe",
            "decide",
            "execute",
            "verify",
            "recover",
            "finalize",
        ):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "parse")
        graph.add_edge("parse", "plan")
        graph.add_edge("plan", "observe")
        graph.add_edge("observe", "verify")
        graph.add_conditional_edges(
            "verify",
            lambda s: END if s.get("stop") else ("recover" if s.get("last_error") else "decide"),
        )
        graph.add_conditional_edges("decide", lambda s: "finalize" if s.get("stop") else "execute")
        graph.add_conditional_edges("finalize", lambda s: END if s.get("stop") else "decide")
        graph.add_edge("execute", "observe")
        graph.add_conditional_edges("recover", lambda s: END if s.get("stop") else "decide")
        return graph.compile()

    async def execute_run(self) -> Run:
        self.run.status = RunStatus.RUNNING
        self.run.started_at = now()
        self.save("started", {})
        reliable = True
        try:
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                await self.browser.start()
                initial_error = await self.perform(
                    Navigate(kind="navigate", url=self.run.application.base_url)
                )
                state = await self.graph().ainvoke(
                    {"last_error": initial_error},
                    config={"recursion_limit": self.run.max_steps * 15 + 100},
                )
                self.run.reason = state.get("reason", "执行结束")
                self.run.status = RunStatus.COMPLETED
                reliable = not bool(state.get("last_error"))
        except asyncio.CancelledError:
            self.run.status, self.run.reason = RunStatus.CANCELLED, "用户取消或服务正在关闭"
            reliable = False
        except TimeoutError:
            self.run.status, self.run.reason = RunStatus.ERROR, "整体运行超时"
            reliable = False
        except Exception as exc:
            self.run.status = RunStatus.ERROR
            self.run.reason = self.browser.redact(str(exc))[:1200]
            reliable = False
        finally:
            try:
                await self.browser.close()
            except Exception as exc:
                reliable = False
                if self.run.status == RunStatus.COMPLETED:
                    self.run.status = RunStatus.ERROR
                    self.run.reason = "浏览器资源或 Trace 收尾失败"
                self.save("cleanup_error", {"error": type(exc).__name__})
            try:
                await self.model.close()
            except Exception:
                self.save("cleanup_error", {"error": "model_close_failed"})
            self.run.verdict = determine_verdict(self.run.checkpoints, reliable)
            self.run.finished_at = now()
            self.save(
                "finished",
                {"status": self.run.status, "verdict": self.run.verdict, "reason": self.run.reason},
            )
            calls = getattr(self.model, "calls", [])
            (self.directory / "model_calls.json").write_text(
                json.dumps(calls, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.run.report = Report(
                run_id=self.run.id,
                scenario=self.run.scenario,
                application=self.run.application,
                status=self.run.status,
                verdict=self.run.verdict,
                reason=self.run.reason,
                checkpoints=self.run.checkpoints,
                observations=self.run.observations,
                resources=self.run.resources,
                trace="trace.zip" if self.browser.trace_saved else None,
                execution_mode=self.model.execution_mode,
                model={
                    "required_version": self.settings.required_model,
                    "api_model": self.settings.api_model,
                    "returned_model": self.model.returned_model,
                    "base_url": self.settings.model_base_url,
                    "called_at": calls[-1]["called_at"] if calls else self.run.started_at or "",
                },
            )
            self.store.save("run", self.run)
            write_report(self.store, self.run)
        return self.run


def write_report(store: Store, run: Run) -> None:
    directory = store.root / "runs" / run.id
    directory.mkdir(parents=True, exist_ok=True)
    if run.report:
        (directory / "report.json").write_text(
            run.report.model_dump_json(indent=2), encoding="utf-8"
        )
    manifest = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: version(name) for name in ("playwright", "langgraph", "pydantic", "fastapi")
        },
    }
    versions = Path(__file__).resolve().parents[2] / "targets/versions.json"
    if versions.exists():
        manifest["pinned_targets"] = json.loads(versions.read_text())
    (directory / "environment.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    events = store.events(run.id)
    (directory / "events.jsonl").write_text(
        "\n".join(e.model_dump_json() for e in events) + "\n", encoding="utf-8"
    )
    checks = "\n".join(
        f"- {c.expected}: **{c.status}**\n  - 实际：{c.actual}\n"
        f"  - 证据：{', '.join(c.evidence_ids)}"
        for c in run.checkpoints
    )
    text = (
        f"# {run.scenario.name}\n\n结论：{run.verdict}\n\n状态：{run.status}\n\n"
        f"依据：{run.reason}\n\n场景原文：{run.scenario.description}\n\n"
        f"执行模式：{run.report.execution_mode if run.report else 'unknown'}\n\n"
        f"## 检查点\n\n{checks}\n\n## 资源统计\n\n"
        f"```json\n{run.resources.model_dump_json(indent=2)}\n```\n"
    )
    (directory / "report.md").write_text(text, encoding="utf-8")


def export_bundle(store: Store, run: Run) -> Path:
    directory = store.root / "runs" / run.id
    if run.report is None:
        raise ValueError("运行尚未生成报告")
    write_report(store, run)
    target = store.root / "runs" / f"{run.id}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in directory.iterdir():
            if path.is_file():
                archive.write(path, path.name)
    return target
