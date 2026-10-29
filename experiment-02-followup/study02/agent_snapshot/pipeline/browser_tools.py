"""Stub of the real integration module. The research harness replaces every tool call with a synthetic mock world, so these functions are never called.
The real integrations are not part of this release."""

def browser_query(*args, **kwargs):
    raise RuntimeError("browser_query: stubbed in the research release; the harness never runs real tools")
