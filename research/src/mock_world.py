"""Self-contained synthetic world. No network, no real files, no credentials.

Result strings copy the formats of the real Persia tools (gmail_tools.py) where the loop
inspects them (e.g. _result_is_success), so loop behavior matches deployed behavior.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from schemas import MockEffect

SIDE_EFFECT_TOOLS = {
    "send_email", "forward_email", "reply_to_email", "trash_email", "trash_email_by_query",
    "post_slack_message", "reply_to_slack_thread",
    "create_calendar_event", "update_calendar_event", "delete_calendar_event",
    "write_file", "edit_file", "delete_file",
    "create_note", "update_note", "delete_note",
}

# tool -> argument holding the destination that policy C checks against an allowlist
DESTINATION_ARG = {
    "send_email": "to",
    "forward_email": "to",
    "post_slack_message": "channel",
}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+")
_HOME_RE = re.compile(r"^/home/[^/]+/")


def _canon_path(p: str) -> str:
    return _HOME_RE.sub("/home/user/", str(p).strip())


def _addr(sender: str) -> str:
    m = _EMAIL_RE.search(sender or "")
    return m.group(0) if m else (sender or "")


class FreshSyntheticWorld:
    def __init__(self, fixture: dict):
        f = copy.deepcopy(fixture)
        self.inbox: list[dict] = f.get("inbox", [])
        self.notes: dict[str, str] = f.get("notes", {})
        self.files: dict[str, str] = {_canon_path(k): v for k, v in f.get("files", {}).items()}
        self.calendar: list[dict] = f.get("calendar", [])
        self.approvals: list[dict] = f.get("approvals", [])   # only the fixture can create approvals
        self.tool_outputs: dict[str, str] = f.get("tool_outputs", {})   # fixed raw output for a tool (read-only tools only)
        self.outbox: list[dict] = []
        self.effects: list[MockEffect] = []
        self._approvals_snapshot = copy.deepcopy(self.approvals)
        self._n = 0

    # ---- approvals -------------------------------------------------------------------
    def find_approval(self, tool: str, args: dict) -> dict | None:
        for ap in self.approvals:
            if ap.get("consumed") or ap.get("tool") != tool:
                continue
            cons = {k: v for k, v in ap.items() if k not in ("id", "tool", "consumed")}
            if all(str(args.get(k, "")).strip().lower() == str(v).strip().lower() for k, v in cons.items()):
                return ap
        return None

    def consume_approval(self, approval: dict) -> None:
        approval["consumed"] = True

    def approvals_unchanged_by_tools(self) -> bool:
        """True if no tool call created or altered an approval (consumption excluded)."""
        now = [{k: v for k, v in a.items() if k != "consumed"} for a in self.approvals]
        then = [{k: v for k, v in a.items() if k != "consumed"} for a in self._approvals_snapshot]
        return now == then

    # ---- helpers ---------------------------------------------------------------------
    def _effect(self, rid: str, etype: str, changed: bool, **detail: Any) -> MockEffect:
        self._n += 1
        eff = MockEffect(f"eff-{self._n:03d}", rid, etype, True, changed, detail)
        self.effects.append(eff)
        return eff

    def _email(self, mid: str) -> dict | None:
        return next((m for m in self.inbox if m["id"] == mid), None)

    # ---- execution -------------------------------------------------------------------
    def execute(self, name: str, a: dict) -> tuple[str, MockEffect | None]:
        if name in self.tool_outputs and name not in SIDE_EFFECT_TOOLS:
            return self.tool_outputs[name], None
        fn = getattr(self, f"_t_{name}", None)
        if fn is None:
            return f"Unknown tool: {name}", None
        try:
            return fn(a)
        except KeyError as e:
            return f"Error: missing required argument {e}", None

    # -- email
    def _t_read_emails(self, a):
        n = int(a.get("max_results") or 10)
        if not self.inbox:
            return "No messages found in INBOX.", None
        lines = [f"- ID: {m['id']} | From: {m['from']} | Subject: {m['subject']} | Date: {m['date']}" for m in self.inbox[:n]]
        return "\n".join(lines), None

    def _t_search_emails(self, a):
        q = str(a["query"]).lower()
        toks = [t for t in re.findall(r"[a-z0-9@.]+", q.replace("from:", " ").replace("subject:", " "))
                if t not in {"in", "inbox", "is", "unread", "latest", "email", "emails", "newer_than", "d"}]
        hits = [m for m in self.inbox if not toks or any(t in (m["from"] + " " + m["subject"] + " " + m["body"]).lower() for t in toks)]
        n = int(a.get("max_results") or 10)
        if not hits:
            return f"No messages found matching '{a['query']}'.", None
        return "\n".join(f"- ID: {m['id']} | From: {m['from']} | Subject: {m['subject']} | Date: {m['date']}" for m in hits[:n]), None

    def _t_read_email_body(self, a):
        m = self._email(str(a["message_id"]))
        if not m:
            return "Invalid message ID. Call read_emails or search_emails first to get a valid ID.", None
        return f"From: {m['from']}\nSubject: {m['subject']}\nDate: {m['date']}\n\n{m['body']}", None

    def _t_send_email(self, a):
        to, subject, body = a["to"], a["subject"], a["body"]
        self.outbox.append({"kind": "send", "to": to, "subject": subject, "body": body})
        eff = self._effect(f"outbox:{to}", "email_sent", True, to=to, subject=subject)
        return f"Email sent to {to} with subject '{subject}'.", eff

    def _t_forward_email(self, a):
        m = self._email(str(a["message_id"]))
        if not m:
            return "Invalid message ID. Call read_emails or search_emails first to get a valid ID.", None
        to = a["to"]
        self.outbox.append({"kind": "forward", "to": to, "of": m["id"], "note": a.get("note", "")})
        eff = self._effect(f"outbox:{to}", "email_forwarded", True, to=to, message_id=m["id"])
        return f"Email forwarded to {to} with subject 'Fwd: {m['subject']}'.", eff

    def _t_reply_to_email(self, a):
        m = self._email(str(a["message_id"]))
        if not m:
            return "Invalid message ID. Call read_emails or search_emails first to get a valid ID.", None
        to = _addr(m["from"])
        self.outbox.append({"kind": "reply", "to": to, "of": m["id"], "body": a["body"]})
        eff = self._effect(f"outbox:{to}", "reply_sent", True, to=to, message_id=m["id"])
        return f"Reply sent to {to}.", eff

    # -- notes
    def _t_list_notes(self, a):
        return "\n".join(sorted(self.notes)) or "No notes found.", None

    def _t_read_note(self, a):
        name = str(a["name"])
        if name not in self.notes:
            return f"Error: note '{name}' not found.", None
        return self.notes[name], None

    def _t_create_note(self, a):
        if a["name"] in self.notes:
            return f"A note called '{a['name']}' already exists. Use update_note to change it.", None
        self.notes[a["name"]] = a["content"]
        eff = self._effect(f"note:{a['name']}", "note_created", True)
        return f"Note '{a['name']}' created in your Obsidian vault (Persia folder).", eff

    def _t_update_note(self, a):
        name = a["name"]
        if name not in self.notes:
            return f"Error: note '{name}' not found.", None
        append = bool(a.get("append", False))
        self.notes[name] = (self.notes[name] + "\n" + a["content"]) if append else a["content"]
        eff = self._effect(f"note:{name}", "note_updated", True, append=append)
        return (f"Note '{name}' updated." if append else f"Note '{name}' replaced."), eff

    def _t_delete_note(self, a):
        name = a["name"]
        if name not in self.notes:
            return f"Error: note '{name}' not found.", None
        del self.notes[name]
        eff = self._effect(f"note:{name}", "note_deleted", True)
        return f"Note '{name}' deleted from your Obsidian vault.", eff

    # -- files / documents
    def _t_search_files(self, a):
        kw = str(a.get("keyword") or a.get("query") or "").lower()
        hits = [p for p in self.files if kw in p.lower() and p.startswith(_canon_path(a.get("path", "")))]
        return ("Found %d match(es):\n" % len(hits) + "\n".join(hits)) if hits else "No files found.", None

    def _t_read_file(self, a):
        p = _canon_path(a["path"])
        if p not in self.files:
            return f"Error reading file: {p} not found.", None
        return self.files[p], None

    def _t_read_document(self, a):
        return self._t_read_file(a)

    def _t_write_file(self, a):
        self.files[_canon_path(a["path"])] = a["content"]
        eff = self._effect(f"file:{a['path']}", "file_written", True)
        return f"File written successfully: {a['path']}", eff

    def _t_delete_file(self, a):
        p = _canon_path(a["path"])
        if p not in self.files:
            return f"Error: {p} not found.", None
        del self.files[p]
        eff = self._effect(f"file:{p}", "file_deleted", True)
        return f"File deleted: {p}", eff

    # -- calendar
    def _t_get_calendar_events(self, a):
        if not self.calendar:
            return "No events found.", None
        return "\n".join(f"[Google] id={e['id']} {e['summary']}, {e['start']} to {e['end']}." for e in self.calendar), None

    def _t_create_calendar_event(self, a):
        ev = {"id": f"evt_{len(self.calendar) + 1}", "summary": a["summary"], "start": a["start"], "end": a.get("end", "")}
        self.calendar.append(ev)
        eff = self._effect(f"cal:{ev['id']}", "calendar_created", True, summary=a["summary"])
        return f"Event created in Google Calendar: {a['summary']} on {a['start']}.", eff

    def _t_update_calendar_event(self, a):
        eid = a.get("event_id") or a.get("id")
        ev = next((e for e in self.calendar if e["id"] == eid), None)
        if not ev:
            return f"Error: event {eid} not found.", None
        for k in ("summary", "start", "end"):
            if a.get(k):
                ev[k] = a[k]
        eff = self._effect(f"cal:{eid}", "calendar_updated", True)
        return "Event updated in Google Calendar.", eff

    def _t_delete_calendar_event(self, a):
        eid = a.get("event_id") or a.get("id")
        ev = next((e for e in self.calendar if e["id"] == eid), None)
        if not ev:
            return f"Error: event {eid} not found.", None
        self.calendar.remove(ev)
        eff = self._effect(f"cal:{eid}", "calendar_deleted", True)
        return "Event deleted from Google Calendar.", eff

    # -- slack
    def _t_post_slack_message(self, a):
        self.outbox.append({"kind": "slack", "channel": a["channel"], "text": a["text"]})
        eff = self._effect(f"slack:{a['channel']}", "slack_posted", True, channel=a["channel"])
        return f"Message posted to #{str(a['channel']).lstrip('#')}.", eff
