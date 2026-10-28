"""Stub of the real integration module. The research harness replaces every tool call with a synthetic mock world, so these functions are never called.
The real integrations are not part of this release."""

def list_task_lists(*args, **kwargs):
    raise RuntimeError("list_task_lists: stubbed in the research release; the harness never runs real tools")

def list_tasks(*args, **kwargs):
    raise RuntimeError("list_tasks: stubbed in the research release; the harness never runs real tools")

def create_task_list(*args, **kwargs):
    raise RuntimeError("create_task_list: stubbed in the research release; the harness never runs real tools")

def create_task(*args, **kwargs):
    raise RuntimeError("create_task: stubbed in the research release; the harness never runs real tools")

def complete_task(*args, **kwargs):
    raise RuntimeError("complete_task: stubbed in the research release; the harness never runs real tools")

def update_task(*args, **kwargs):
    raise RuntimeError("update_task: stubbed in the research release; the harness never runs real tools")

def delete_task(*args, **kwargs):
    raise RuntimeError("delete_task: stubbed in the research release; the harness never runs real tools")
