"""Trusted lineage ledger. Deterministic; the model can neither read nor write it.

Records what entered the agent's context (with environment labels) and answers three questions for the dispatcher:
  origin(value)           where did this argument value first appear: user | trusted | untrusted | unknown
  max_sensitivity         the highest sensitivity of anything read in this episode
  overlap(text)           how much of `text` shares n-grams with private text read in this episode (or written from it)
"""

from __future__ import annotations

import re

SHINGLE = 4
_WORD = re.compile(r"[a-z0-9]+")
_SPECIFIC = re.compile(r"[a-z0-9][a-z0-9\-]{2,}")


def norm(v) -> str:
    return re.sub(r"\s+", " ", str(v).strip().lower().replace("#", "")).replace("/home/user/", "/home/user/")


def shingles(text: str, k: int = SHINGLE) -> set[tuple]:
    toks = _WORD.findall(str(text).lower())
    return {tuple(toks[i:i + k]) for i in range(max(0, len(toks) - k + 1))}


def specific_tokens(text: str) -> set[str]:
    """Tokens that carry specific information: at least 3 characters and at least one digit (figures, codes). Thousands separators and $ are removed first."""
    t = re.sub(r"(?<=\d),(?=\d{3})", "", str(text).lower().replace("$", ""))
    return {x for x in _SPECIFIC.findall(t) if any(ch.isdigit() for ch in x)}


class Ledger:
    def __init__(self, user_request: str, grants: dict):
        import json
        self.user_text = norm(user_request) + " " + norm(json.dumps(grants))
        self.trusted: list[str] = []
        self.untrusted: list[str] = []
        self.private: list[str] = []
        self.max_sensitivity = "public"
        self.read_artifacts: list[dict] = []
        self.public_tokens: set[str] = specific_tokens(user_request) | specific_tokens(json.dumps(grants))
        self.private_tokens: set[str] = set()

    # ---- updates (called by the dispatcher after a tool ran) -----------------------------
    def observe_reads(self, reads: list[dict]) -> None:
        for r in reads:
            self.read_artifacts.append({k: r[k] for k in ("artifact", "trust", "sensitivity")})
            (self.untrusted if r["trust"] == "untrusted" else self.trusted).append(norm(r["text"]))
            if r["sensitivity"] == "private":
                self.private.append(r["text"])
                self.max_sensitivity = "private"
                self.private_tokens |= specific_tokens(r["text"])
            else:
                self.public_tokens |= specific_tokens(r["text"])

    def observe_write(self, text: str, threshold: int) -> None:
        """Derived artifact: text written to an internal resource that overlaps private text becomes private text itself."""
        if text and self.overlap(text) >= threshold:
            self.private.append(text)

    # ---- queries ---------------------------------------------------------------------------
    def origin(self, value) -> str:
        v = norm(value)
        if not v:
            return "unknown"
        if v in self.user_text:
            return "user"
        if any(v in t for t in self.trusted):
            return "trusted"
        if any(v in t for t in self.untrusted):
            return "untrusted"
        return "unknown"

    def overlap(self, text: str) -> int:
        out = shingles(text)
        if not out:
            return 0
        return max((len(out & shingles(p)) for p in self.private), default=0)

    def private_only_hits(self, text: str) -> set[str]:
        """Specific tokens in `text` that occur in private text read this episode and nowhere in the user request, grants or non-private artifacts read."""
        return specific_tokens(text) & (self.private_tokens - self.public_tokens)

    def summary(self) -> dict:
        return {"max_sensitivity": self.max_sensitivity, "artifacts_read": len(self.read_artifacts),
                "untrusted_artifacts_read": sum(a["trust"] == "untrusted" for a in self.read_artifacts)}
