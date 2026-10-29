"""Study 02 world: the Study 01 mock world (frozen copy in mock_world_base.py) plus artifact labels, read tracking and a final-state snapshot.

Labels are environment-assigned fixture data (like file permissions or DLP tags). The model cannot create or change them.
fixture["labels"] maps "email:<id>", "note:<name>", "file:<canonical path>", "calendar", "tool_output:<tool>" to {"trust","sensitivity"}.
"""

from __future__ import annotations

import copy

from mock_world_base import FreshSyntheticWorld, _addr, _canon_path

DEFAULT_LABEL = {"email": ("untrusted", "public"), "note": ("user", "public"), "file": ("untrusted", "public"),
                 "calendar": ("user", "public"), "tool_output": ("untrusted", "public")}
EXTERNAL_TOOLS = {"send_email", "forward_email", "reply_to_email", "post_slack_message", "reply_to_slack_thread"}


class World(FreshSyntheticWorld):
    def __init__(self, fixture: dict):
        super().__init__(fixture)
        self.labels: dict[str, dict] = copy.deepcopy(fixture.get("labels", {}))
        self.last_reads: list[dict] = []
        self._initial = self.snapshot()

    # ---- labels and reads ---------------------------------------------------------------
    def label(self, key: str) -> dict:
        if key in self.labels:
            return self.labels[key]
        trust, sens = DEFAULT_LABEL[key.split(":", 1)[0]]
        return {"trust": trust, "sensitivity": sens}

    def _read(self, key: str, text: str) -> None:
        lab = self.label(key)
        self.last_reads.append({"artifact": key, "trust": lab["trust"], "sensitivity": lab["sensitivity"], "text": text})

    def execute(self, name: str, a: dict):
        self.last_reads = []
        result, eff = super().execute(name, a)
        if name in self.tool_outputs and name not in {"send_email"}:
            self._read(f"tool_output:{name}", result)
        return result, eff

    # ---- read tools record what entered the agent's context ----------------------------------
    def _t_read_emails(self, a):
        res, eff = super()._t_read_emails(a)
        for m in self.inbox[: int(a.get("max_results") or 10)]:
            self._read(f"email:{m['id']}", f"From: {m['from']} | Subject: {m['subject']}")
        return res, eff

    def _t_search_emails(self, a):
        res, eff = super()._t_search_emails(a)
        for m in self.inbox:
            if f"ID: {m['id']}" in res:
                self._read(f"email:{m['id']}", f"From: {m['from']} | Subject: {m['subject']}")
        return res, eff

    def _t_read_email_body(self, a):
        res, eff = super()._t_read_email_body(a)
        m = self._email(str(a.get("message_id", "")))
        if m:
            self._read(f"email:{m['id']}", res)
        return res, eff

    def _t_read_note(self, a):
        res, eff = super()._t_read_note(a)
        if str(a.get("name", "")) in self.notes:
            self._read(f"note:{a['name']}", res)
        return res, eff

    def _t_read_file(self, a):
        res, eff = super()._t_read_file(a)
        p = _canon_path(a.get("path", ""))
        if p in self.files:
            self._read(f"file:{p}", res)
        return res, eff

    def _t_get_calendar_events(self, a):
        res, eff = super()._t_get_calendar_events(a)
        if self.calendar:
            self._read("calendar", res)
        return res, eff

    # ---- destinations ---------------------------------------------------------------------
    def destination_of(self, name: str, args: dict) -> str | None:
        if name in ("send_email", "forward_email"):
            return args.get("to")
        if name in ("post_slack_message", "reply_to_slack_thread"):
            return args.get("channel")
        if name == "reply_to_email":
            m = self._email(str(args.get("message_id", "")))
            return _addr(m["from"]) if m else None
        return None

    # ---- final state, for the independent evaluator -------------------------------------------
    def snapshot(self) -> dict:
        return {"outbox": copy.deepcopy(self.outbox), "notes": copy.deepcopy(self.notes), "files": copy.deepcopy(self.files),
                "calendar": copy.deepcopy(self.calendar)}

    def initial_snapshot(self) -> dict:
        return copy.deepcopy(self._initial)
