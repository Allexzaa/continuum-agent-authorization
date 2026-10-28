"""Google Tasks API v1 tools for Persia.

All functions return plain strings suitable for LLM consumption.
List name resolution is fuzzy and cached for 60 seconds per call.
"""

import time
from datetime import timezone
from pathlib import Path
from typing import Optional

from dateutil import parser as _dateparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

_TOKEN_FILE = Path(__file__).parent.parent / "config" / "google_token.json"

# Module-level cache: {list_title_lower: (list_id, canonical_title, timestamp)}
_list_cache: dict = {}
_LIST_CACHE_TTL = 60.0


def _get_tasks_service():
    creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _TOKEN_FILE.write_text(creds.to_json())
    return build("tasks", "v1", credentials=creds)


def _tasks_available() -> bool:
    return _TOKEN_FILE.exists()


def _fetch_all_lists(service) -> list[dict]:
    result = service.tasklists().list(maxResults=100).execute()
    return result.get("items", [])


def _resolve_list(service, name: str) -> tuple[str, str]:
    """Return (list_id, canonical_title) for the named task list.
    Falls back to 'My Tasks' if name is empty. Raises ValueError if not found."""
    name = (name or "My Tasks").strip()
    now = time.monotonic()

    # Check cache
    name_lower = name.lower()
    cached = _list_cache.get(name_lower)
    if cached and (now - cached[2]) < _LIST_CACHE_TTL:
        return cached[0], cached[1]

    lists = _fetch_all_lists(service)

    # Exact match first (case-insensitive)
    for lst in lists:
        if lst["title"].lower() == name_lower:
            _list_cache[name_lower] = (lst["id"], lst["title"], now)
            return lst["id"], lst["title"]

    # Substring match
    for lst in lists:
        if name_lower in lst["title"].lower() or lst["title"].lower() in name_lower:
            _list_cache[name_lower] = (lst["id"], lst["title"], now)
            return lst["id"], lst["title"]

    titles = ", ".join(lst["title"] for lst in lists)
    raise ValueError(f"Task list '{name}' not found. Available lists: {titles}")


def _parse_due(due_str: str) -> Optional[str]:
    """Parse a natural language date string into RFC3339 midnight UTC.
    Returns None if due_str is empty or unparseable."""
    if not due_str or not due_str.strip():
        return None
    try:
        dt = _dateparser.parse(due_str, fuzzy=True)
        if dt is None:
            return None
        # Google Tasks is date-only — always midnight UTC
        dt_utc = dt.replace(hour=0, minute=0, second=0, microsecond=0,
                            tzinfo=timezone.utc)
        return dt_utc.strftime("%Y-%m-%dT00:00:00.000Z")
    except Exception:
        return None


def _format_task(t: dict) -> str:
    parts = [f"[{t.get('status', 'needsAction')}] {t.get('title', '(no title)')} (ID: {t['id']})"]
    if t.get("due"):
        due_date = t["due"][:10]
        parts.append(f"  Due: {due_date}")
    if t.get("notes"):
        parts.append(f"  Notes: {t['notes'][:120]}")
    return "\n".join(parts)


# ── Public tools ───────────────────────────────────────────────────────────────

def create_task_list(name: str) -> str:
    """Create a new Google Task list with the given name."""
    if not _tasks_available():
        return "Google Tasks not available — run scripts/auth_google.py first."
    if not name.strip():
        return "Error: list name is required."
    try:
        svc = _get_tasks_service()
        result = svc.tasklists().insert(body={"title": name.strip()}).execute()
        # Invalidate cache so the new list is found immediately
        _list_cache.clear()
        return f"Task list '{result['title']}' created successfully (ID: {result['id']})."
    except Exception as e:
        return f"Error creating task list: {e}"


def list_task_lists() -> str:
    """List all Google Task list names."""
    if not _tasks_available():
        return "Google Tasks not available — run scripts/auth_google.py first."
    try:
        svc = _get_tasks_service()
        lists = _fetch_all_lists(svc)
        if not lists:
            return "No task lists found in your Google account."
        lines = [f"- {lst['title']}" for lst in lists]
        return "Your Google Task lists:\n" + "\n".join(lines)
    except Exception as e:
        return f"Error fetching task lists: {e}"


def list_tasks(list_name: str = "My Tasks", show_completed: bool = False) -> str:
    """List tasks in a named Google Task list.
    Must call this before complete_task or delete_task to get valid task IDs."""
    if not _tasks_available():
        return "Google Tasks not available — run scripts/auth_google.py first."
    try:
        svc = _get_tasks_service()
        list_id, canonical = _resolve_list(svc, list_name)
        kwargs: dict = {
            "tasklist": list_id,
            "showCompleted": show_completed,
            "showHidden": show_completed,
            "maxResults": 100,
        }
        result = svc.tasks().list(**kwargs).execute()
        tasks = result.get("items", [])
        if not tasks:
            label = "tasks" if show_completed else "open tasks"
            return f"No {label} found in '{canonical}'."
        lines = [_format_task(t) for t in tasks]
        header = f"Tasks in '{canonical}' ({len(tasks)} found):"
        return header + "\n" + "\n".join(lines)
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Error listing tasks: {e}"


def create_task(title: str, list_name: str = "My Tasks",
                notes: str = "", due: str = "") -> str:
    """Create a new Google Task. Due date accepts natural language (Friday, April 30, etc.)."""
    if not _tasks_available():
        return "Google Tasks not available — run scripts/auth_google.py first."
    if not title.strip():
        return "Error: task title is required."
    try:
        svc = _get_tasks_service()
        list_id, canonical = _resolve_list(svc, list_name)
        body: dict = {"title": title.strip(), "status": "needsAction"}
        if notes.strip():
            body["notes"] = notes.strip()
        due_rfc = _parse_due(due)
        if due_rfc:
            body["due"] = due_rfc
        task = svc.tasks().insert(tasklist=list_id, body=body).execute()
        due_note = f" Due: {due_rfc[:10]}." if due_rfc else ""
        return f"Task created in '{canonical}': '{task['title']}' (ID: {task['id']}).{due_note}"
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Error creating task: {e}"


def complete_task(task_id: str, list_name: str = "My Tasks") -> str:
    """Mark a Google Task as completed. Call list_tasks first to get the task ID."""
    if not _tasks_available():
        return "Google Tasks not available — run scripts/auth_google.py first."
    task_id = (task_id or "").strip()
    if not task_id:
        return "Error: task_id is required. Call list_tasks first to get valid IDs."
    try:
        svc = _get_tasks_service()
        list_id, canonical = _resolve_list(svc, list_name)
        # Fetch current task to get title for confirmation message
        task = svc.tasks().get(tasklist=list_id, task=task_id.strip()).execute()
        from datetime import datetime
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        svc.tasks().patch(
            tasklist=list_id,
            task=task_id.strip(),
            body={"status": "completed", "completed": now_utc},
        ).execute()
        return f"Marked complete: '{task.get('title', task_id)}' in '{canonical}'."
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Error completing task: {e}"


def update_task(task_id: str, list_name: str = "My Tasks",
                title: str = "", notes: str = "", due: str = "") -> str:
    """Edit an existing Google Task's title, notes, or due date.
    Pass only the fields you want to change. Call list_tasks first to get the task ID."""
    if not _tasks_available():
        return "Google Tasks not available — run scripts/auth_google.py first."
    task_id = (task_id or "").strip()
    if not task_id:
        return "Error: task_id is required. Call list_tasks first to get valid IDs."
    body: dict = {}
    if title.strip():
        body["title"] = title.strip()
    if notes.strip():
        body["notes"] = notes.strip()
    due_rfc = _parse_due(due)
    if due_rfc:
        body["due"] = due_rfc
    if not body:
        return "Nothing to update — provide at least one of: title, notes, due."
    try:
        svc = _get_tasks_service()
        list_id, canonical = _resolve_list(svc, list_name)
        task = svc.tasks().patch(
            tasklist=list_id, task=task_id.strip(), body=body
        ).execute()
        changes = []
        if title.strip():
            changes.append(f"title → '{task.get('title')}'")
        if notes.strip():
            changes.append("notes updated")
        if due_rfc:
            changes.append(f"due → {due_rfc[:10]}")
        return f"Task updated in '{canonical}': {', '.join(changes)}."
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Error updating task: {e}"


def delete_task(task_id: str, list_name: str = "My Tasks") -> str:
    """Permanently delete a Google Task. Call list_tasks first to get the task ID.
    This action is irreversible — confirmation is required before it runs."""
    if not _tasks_available():
        return "Google Tasks not available — run scripts/auth_google.py first."
    task_id = (task_id or "").strip()
    if not task_id:
        return "Error: task_id is required. Call list_tasks first to get valid IDs."
    try:
        svc = _get_tasks_service()
        list_id, canonical = _resolve_list(svc, list_name)
        task = svc.tasks().get(tasklist=list_id, task=task_id.strip()).execute()
        title = task.get("title", task_id)
        svc.tasks().delete(tasklist=list_id, task=task_id.strip()).execute()
        return f"Task permanently deleted from '{canonical}': '{title}'."
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Error deleting task: {e}"
