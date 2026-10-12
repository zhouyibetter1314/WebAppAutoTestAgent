from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


def new_id() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(UTC).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    ERROR = "error"


TERMINAL = {RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.INTERRUPTED, RunStatus.ERROR}


class ApplicationInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: HttpUrl
    username_env: str = ""
    password_env: str = ""
    version: str = ""


class Application(ApplicationInput):
    id: str = Field(default_factory=new_id)


class ScenarioInput(StrictModel):
    application_id: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=12000)
    source: str = "user"


class Scenario(ScenarioInput):
    id: str = Field(default_factory=new_id)


class RunRequest(StrictModel):
    scenario_id: str
    max_steps: int = Field(default=35, ge=1, le=35)


class LocatorSpec(StrictModel):
    by: Literal["role", "label", "text", "placeholder", "test_id", "css"]
    value: str = Field(min_length=1, max_length=500)
    name: str | None = None


class Navigate(StrictModel):
    kind: Literal["navigate"]
    url: HttpUrl


class Click(StrictModel):
    kind: Literal["click"]
    target: LocatorSpec


class Fill(StrictModel):
    kind: Literal["fill"]
    target: LocatorSpec
    value: str = Field(max_length=10000)


class Select(StrictModel):
    kind: Literal["select"]
    target: LocatorSpec
    value: str


class Scroll(StrictModel):
    kind: Literal["scroll"]
    delta_y: int = Field(ge=-2000, le=2000)


class Drag(StrictModel):
    kind: Literal["drag"]
    source: LocatorSpec
    destination: LocatorSpec


class Press(StrictModel):
    kind: Literal["press"]
    target: LocatorSpec
    key: Literal["Enter", "Tab", "Escape", "ArrowDown", "ArrowUp", "Space"]


Action = Annotated[
    Navigate | Click | Fill | Select | Scroll | Drag | Press, Field(discriminator="kind")
]


class Checkpoint(StrictModel):
    id: str
    expected: str = Field(min_length=1)
    status: Literal["pending", "satisfied", "violated"] = "pending"
    actual: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class ScenarioSpec(StrictModel):
    preconditions: list[str]
    goals: list[str]
    checkpoints: list[Checkpoint] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_pending(self) -> "ScenarioSpec":
        ids = [c.id for c in self.checkpoints]
        if len(ids) != len(set(ids)):
            raise ValueError("Checkpoint IDs must be unique")
        if any(c.status != "pending" or c.evidence_ids for c in self.checkpoints):
            raise ValueError("Initial checkpoints must be pending without evidence")
        return self


class PlanStep(StrictModel):
    instruction: str
    evidence_needed: str


class Plan(StrictModel):
    steps: list[PlanStep] = Field(min_length=1)


class Decision(StrictModel):
    reason: str
    action: Action | None = None
    wait_ms: int = Field(default=0, ge=0, le=3000)
    finish: bool = False

    @model_validator(mode="after")
    def one_choice(self) -> "Decision":
        if sum([self.action is not None, self.wait_ms > 0, self.finish]) != 1:
            raise ValueError("Choose exactly one action, wait, or finish")
        return self


class CheckUpdate(StrictModel):
    id: str
    status: Literal["pending", "satisfied", "violated"]
    actual: str
    evidence_ids: list[str]
    quote: str = ""


class Verification(StrictModel):
    checks: list[CheckUpdate]


class Observation(StrictModel):
    id: str = Field(default_factory=new_id)
    created_at: str = Field(default_factory=now)
    url: str
    title: str
    aria: str
    screenshot: str
    snapshot: str


class Resources(StrictModel):
    browser_steps: int = 0
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_complete: bool = True
    elapsed_seconds: float = 0


class Report(StrictModel):
    run_id: str
    scenario: Scenario
    application: Application
    status: RunStatus
    verdict: Verdict
    reason: str
    checkpoints: list[Checkpoint]
    observations: list[Observation]
    resources: Resources
    trace: str | None
    execution_mode: str
    model: dict[str, str]


class Run(StrictModel):
    id: str = Field(default_factory=new_id)
    scenario: Scenario
    application: Application
    max_steps: int = 35
    status: RunStatus = RunStatus.QUEUED
    verdict: Verdict | None = None
    reason: str = ""
    created_at: str = Field(default_factory=now)
    started_at: str | None = None
    finished_at: str | None = None
    resources: Resources = Field(default_factory=Resources)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    report: Report | None = None


class Event(StrictModel):
    sequence: int
    run_id: str
    kind: str
    created_at: str
    data: dict


class ImportScenarios(StrictModel):
    scenarios: list[ScenarioInput] = Field(min_length=1, max_length=100)


class ScenarioFile(StrictModel):
    application: ApplicationInput
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = "self-authored"


class SettingsInfo(StrictModel):
    model_configured: bool
    required_model: str
    api_model: str
    base_url: str
    max_steps: int
    headless: bool
    execution_mode: str
