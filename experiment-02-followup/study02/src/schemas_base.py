# FROZEN COPY of research/src/schemas.py (Study 01), unmodified except this line.
"""Schemas for the Persia AI-control pilot (plain dataclasses, JSON-serializable)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

UNTRUSTED_PLACEHOLDER = "{{UNTRUSTED}}"


def canonical_hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _substitute(obj: Any, replacement: str) -> Any:
    if isinstance(obj, str):
        return obj.replace(UNTRUSTED_PLACEHOLDER, replacement)
    if isinstance(obj, list):
        return [_substitute(x, replacement) for x in obj]
    if isinstance(obj, dict):
        return {k: _substitute(v, replacement) for k, v in obj.items()}
    return obj


@dataclass
class Case:
    case_id: str
    family: str
    pair_id: str                      # adversarial case and its benign twin share a pair_id
    kind: str                         # "adversarial" | "benign_twin" | "benign_authorized"
    user_task: str
    untrusted_surface: str
    untrusted_content: str            # "" for benign twins
    available_mock_tools: list[str]
    allowed_actions: list[dict]       # constraints compared against tool args; may carry requires_approval
    forbidden_actions: list[dict]     # {"tool": ..., optional arg constraints}
    expected_task_outcome: str
    success_criteria: dict            # response_facts / min_facts / required_effects
    required_approval_events: list[dict]
    dataset_split: str
    attack_success_ground_truth: str
    fixture: dict                     # contains UNTRUSTED_PLACEHOLDER where the injected text goes
    notes: str = ""

    @staticmethod
    def from_dict(d: dict) -> "Case":
        return Case(**d)

    def resolved_fixture(self) -> dict:
        return _substitute(self.fixture, self.untrusted_content)

    def fixture_hash(self) -> str:
        return canonical_hash(self.resolved_fixture())


@dataclass
class PolicyVerdict:
    decision: str                     # "allow" | "deny" | "needs_approval"
    policy_rule: str
    reason_code: str
    approval_event_id: str | None = None


@dataclass
class MockEffect:
    mock_effect_id: str
    resource_id: str
    type: str
    occurred: bool
    changed_synthetic_state: bool
    detail: dict = field(default_factory=dict)


@dataclass
class ToolAttempt:
    round_index: int
    proposed_tool: str
    proposed_args: dict
    validated_args: bool
    authorization_scope: str
    source_of_instruction_heuristic: str   # untrusted_content | user_task | unknown
    verdict: dict
    effect: dict | None
    result_preview: str


@dataclass
class RunRecord:
    run_id: str
    case_id: str
    condition: str
    trial: int
    timestamp_utc: str
    fixture_hash: str
    git_commit: str
    git_dirty: bool
    model: dict
    attempts: list[dict]
    proposed_calls: list[dict]        # everything the model proposed, before suppression/authorization
    suppressed_events: list[dict]
    model_rounds: list[dict]          # raw model output per round (content truncated), for failure analysis
    effects: list[dict]
    final_response: str
    outcomes: dict
    error: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)
