"""Stub of the real integration module. The research harness replaces every tool call with a synthetic mock world, so these functions are never called.
The real integrations are not part of this release."""

def get_calendar_events(*args, **kwargs):
    raise RuntimeError("get_calendar_events: stubbed in the research release; the harness never runs real tools")

def create_calendar_event(*args, **kwargs):
    raise RuntimeError("create_calendar_event: stubbed in the research release; the harness never runs real tools")

def update_calendar_event(*args, **kwargs):
    raise RuntimeError("update_calendar_event: stubbed in the research release; the harness never runs real tools")

def delete_calendar_event(*args, **kwargs):
    raise RuntimeError("delete_calendar_event: stubbed in the research release; the harness never runs real tools")
