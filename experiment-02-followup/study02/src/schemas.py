"""Study 02 schemas. The agent-visible case (Case2) holds no oracle information: no prohibited outcomes, no canaries, no expected end state.
Those live in oracle/*.jsonl and are read only by evaluator.py."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from schemas_base import MockEffect, PolicyVerdict, UNTRUSTED_PLACEHOLDER, _substitute, canonical_hash  # noqa: F401


@dataclass
class Case2:
    case_id: str
    family: str
    pair_id: str                 # an attack, its benign twin and near-misses may share a pair_id
    kind: str                    # attack | benign_twin | near_miss | control
    split: str                   # dev | validation | test
    user_request: str            # the only text the agent receives as the user turn
    user_grants: dict            # trusted grant record: tools, destinations, resources, private_destinations, declassify
    available_tools: list[str]
    untrusted_content: str       # "" for benign twins and near-misses
    fixture: dict                # world state incl. "labels"; contains UNTRUSTED_PLACEHOLDER where the injected text goes
    notes: str = ""

    @staticmethod
    def from_dict(d: dict) -> "Case2":
        return Case2(**d)

    def resolved_fixture(self) -> dict:
        return _substitute(self.fixture, self.untrusted_content)

    def case_hash(self) -> str:
        return canonical_hash({"fixture": self.resolved_fixture(), "request": self.user_request, "grants": self.user_grants,
                               "tools": self.available_tools})


@dataclass
class OracleEntry:
    """Evaluator-only. Never imported by policies, lineage or adapter."""
    case_id: str
    prohibited: list[dict]       # predicates over the final world state
    required: list[dict]         # predicates for the expected benign end state
    canaries: list[str]
    exposure_artifacts: list[str] = field(default_factory=list)   # artifact keys whose reading means the agent was exposed to the payload/private data
    notes: str = ""

    @staticmethod
    def from_dict(d: dict) -> "OracleEntry":
        return OracleEntry(**d)


def to_json(obj) -> str:
    return json.dumps(asdict(obj), ensure_ascii=False)
