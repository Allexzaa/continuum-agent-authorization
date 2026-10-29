"""Stub of the real integration module. The research harness replaces every tool call with a synthetic mock world, so these functions are never called.
The real integrations are not part of this release."""

def list_notes(*args, **kwargs):
    raise RuntimeError("list_notes: stubbed in the research release; the harness never runs real tools")

def create_note(*args, **kwargs):
    raise RuntimeError("create_note: stubbed in the research release; the harness never runs real tools")

def read_note(*args, **kwargs):
    raise RuntimeError("read_note: stubbed in the research release; the harness never runs real tools")

def update_note(*args, **kwargs):
    raise RuntimeError("update_note: stubbed in the research release; the harness never runs real tools")

def delete_note(*args, **kwargs):
    raise RuntimeError("delete_note: stubbed in the research release; the harness never runs real tools")

def list_todos(*args, **kwargs):
    raise RuntimeError("list_todos: stubbed in the research release; the harness never runs real tools")

def add_todo(*args, **kwargs):
    raise RuntimeError("add_todo: stubbed in the research release; the harness never runs real tools")

def complete_todo(*args, **kwargs):
    raise RuntimeError("complete_todo: stubbed in the research release; the harness never runs real tools")

def delete_todo(*args, **kwargs):
    raise RuntimeError("delete_todo: stubbed in the research release; the harness never runs real tools")
