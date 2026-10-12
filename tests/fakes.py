import asyncio

from webapp_auto_test_agent.schemas import Resources


class FakeModel:
    execution_mode = "test-double"
    returned_model = "deterministic-fixture"

    def __init__(self, outcome="satisfied", bad_locator=False, delay=0, invalid_evidence=False):
        self.resources = Resources()
        self.outcome, self.bad_locator, self.delay = outcome, bad_locator, delay
        self.invalid_evidence = invalid_evidence
        self.closed = False

    async def ask(self, phase, payload, schema):
        self.resources.model_requests += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if phase == "parse_scenario":
            value = {
                "preconditions": [],
                "goals": ["create"],
                "checkpoints": [{"id": "created", "expected": "Course Test created"}],
            }
        elif phase == "plan":
            value = {"steps": [{"instruction": "Create project", "evidence_needed": "main text"}]}
        elif phase == "next_action":
            value = {
                "reason": "Create",
                "action": {
                    "kind": "click",
                    "target": {
                        "by": "role",
                        "value": "button",
                        "name": "Missing" if self.bad_locator else "Create",
                    },
                },
            }
        else:
            last = payload["observations"][-1]
            value = {
                "checks": [
                    {
                        "id": "created",
                        "status": self.outcome,
                        "actual": "Observed Course Test created",
                        "quote": "Course Test created",
                        "evidence_ids": ["invented"] if self.invalid_evidence else [last["id"]],
                    }
                ]
            }
        return schema.model_validate(value)

    async def close(self):
        self.closed = True
