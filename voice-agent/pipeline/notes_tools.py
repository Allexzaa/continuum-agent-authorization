import json
import os
from datetime import datetime
from pathlib import Path

_NOTES_DIR = Path(os.getenv("NOTES_DIR", str(Path.home() / "Documents" / "Obsidian Vault")))
_PERSIA_DIR = _NOTES_DIR / "Persia"
_TODOS_FILE = _PERSIA_DIR / "todos.json"


def _ensure_dir():
    _NOTES_DIR.mkdir(parents=True, exist_ok=True)
    _PERSIA_DIR.mkdir(exist_ok=True)


def _all_notes() -> list[Path]:
    """Return all .md files in the full vault, sorted by name."""
    return sorted(_NOTES_DIR.rglob("*.md"), key=lambda p: p.stem.lower())


def _find_note(name: str) -> Path | None:
    """Find a note anywhere in the vault by exact stem match, then fuzzy."""
    name_clean = name.strip()
    target = name_clean if name_clean.endswith(".md") else name_clean + ".md"
    # 1. Exact filename match anywhere in vault
    for p in _all_notes():
        if p.name.lower() == target.lower():
            return p
    # 2. Substring match on stem
    lower = name_clean.lower()
    for p in _all_notes():
        if lower in p.stem.lower():
            return p
    return None


def _new_note_path(name: str) -> Path:
    """Path for a newly created note — always goes into Persia/ subfolder."""
    safe = name.strip().replace("/", "-").replace("\\", "-")
    if not safe.endswith(".md"):
        safe += ".md"
    return _PERSIA_DIR / safe


def _frontmatter(name: str, tags: list, created: str = None, updated: str = None) -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    lines = ["---"]
    lines.append(f"title: {name}")
    lines.append(f"created: {created or now}")
    if updated:
        lines.append(f"updated: {updated}")
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append(f"source: Persia")
    lines.append("---")
    return "\n".join(lines)


def _load_todos() -> list:
    if not _TODOS_FILE.exists():
        return []
    try:
        return json.loads(_TODOS_FILE.read_text())
    except Exception:
        return []


def _save_todos(todos: list):
    _ensure_dir()
    _TODOS_FILE.write_text(json.dumps(todos, indent=2))


# ── Note tools ───────────────────────────────────────────────────────────────

def list_notes() -> str:
    """List all notes in the full Obsidian vault."""
    _ensure_dir()
    notes = _all_notes()
    # Exclude todos.json (not a note) and system files
    notes = [p for p in notes if p.name != "todos.md"]
    if not notes:
        return "No notes found in your Obsidian vault."
    lines = []
    for p in notes:
        rel = p.relative_to(_NOTES_DIR)
        # Show as "FolderName / NoteName" or just "NoteName" if at root
        parts = rel.parts
        if len(parts) > 1:
            lines.append(f"- {' / '.join(parts[:-1])} / {p.stem}")
        else:
            lines.append(f"- {p.stem}")
    return f"Notes in your vault ({len(lines)} total):\n" + "\n".join(lines)


def create_note(name: str, content: str, tags: str = "") -> str:
    """Create a new note in the Persia subfolder."""
    _ensure_dir()
    path = _new_note_path(name)
    if path.exists():
        return f"A note called '{name}' already exists. Use update_note to change it."
    tag_list = ["persia"] + [t.strip() for t in tags.split(",") if t.strip()]
    fm = _frontmatter(name, tag_list)
    path.write_text(f"{fm}\n\n{content}\n")
    return f"Note '{name}' created in your Obsidian vault (Persia folder)."


def read_note(name: str) -> str:
    """Read a note from anywhere in the vault by name."""
    path = _find_note(name)
    if path is None:
        return f"No note called '{name}' found. Use list_notes to see what exists."
    content = path.read_text()
    rel = path.relative_to(_NOTES_DIR)
    return (
        f"Note '{path.stem}' ({rel}):\n"
        f"--- NOTE CONTENT START ---\n"
        f"{content}\n"
        f"--- NOTE CONTENT END ---"
    )


def update_note(name: str, content: str, append: bool = False) -> str:
    """Update a note anywhere in the vault. append=True adds content, False replaces it."""
    _ensure_dir()
    path = _find_note(name)
    if path is None:
        return f"No note called '{name}' found. Use create_note to make a new one."
    today = datetime.now().strftime("%Y-%m-%d")
    existing = path.read_text()
    if append:
        if "updated:" in existing:
            lines = existing.splitlines()
            lines = [f"updated: {today}" if l.startswith("updated:") else l for l in lines]
            existing = "\n".join(lines)
        else:
            existing = existing.replace("source: Persia", f"updated: {today}\nsource: Persia", 1)
        path.write_text(existing.rstrip() + f"\n\n{content}\n")
        return f"Note '{name}' updated."
    else:
        created = today
        for line in existing.splitlines():
            if line.startswith("created:"):
                created = line.split(":", 1)[1].strip()
                break
        tags = ["persia"]
        for line in existing.splitlines():
            if line.startswith("tags:"):
                raw = line.split(":", 1)[1].strip().strip("[]")
                tags = [t.strip() for t in raw.split(",") if t.strip()]
                break
        fm = _frontmatter(name, tags, created=created, updated=today)
        path.write_text(f"{fm}\n\n{content}\n")
        return f"Note '{name}' replaced."


def delete_note(name: str) -> str:
    """Delete a note from anywhere in the vault."""
    path = _find_note(name)
    if path is None:
        return f"No note called '{name}' found."
    path.unlink()
    return f"Note '{name}' deleted from your Obsidian vault."


# ── Todo tools ───────────────────────────────────────────────────────────────

def list_todos(list_name: str = "") -> str:
    todos = _load_todos()
    if list_name:
        todos = [t for t in todos if t.get("list", "").lower() == list_name.lower()]
    if not todos:
        return "No todos found." if not list_name else f"No todos in list '{list_name}'."
    lists = {}
    for t in todos:
        lists.setdefault(t.get("list", "General"), []).append(t)
    lines = []
    for lst, items in lists.items():
        lines.append(f"{lst}:")
        for t in items:
            status = "✓" if t.get("done") else "○"
            lines.append(f"  {status} [{t['id']}] {t['text']}")
    return "\n".join(lines)


def add_todo(text: str, list_name: str = "General") -> str:
    todos = _load_todos()
    new_id = max((t["id"] for t in todos), default=0) + 1
    todos.append({"id": new_id, "list": list_name, "text": text, "done": False})
    _save_todos(todos)
    return f"Added to {list_name}: '{text}' (ID {new_id})"


def complete_todo(todo_id: int) -> str:
    todos = _load_todos()
    for t in todos:
        if t["id"] == todo_id:
            t["done"] = True
            _save_todos(todos)
            return f"Marked done: '{t['text']}'"
    return f"No todo with ID {todo_id} found. Use list_todos to see IDs."


def delete_todo(todo_id: int) -> str:
    todos = _load_todos()
    before = len(todos)
    todos = [t for t in todos if t["id"] != todo_id]
    if len(todos) == before:
        return f"No todo with ID {todo_id} found."
    _save_todos(todos)
    return f"Todo {todo_id} deleted."
