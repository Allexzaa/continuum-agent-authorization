"""Stub of the real integration module. The research harness replaces every tool call with a synthetic mock world, so these functions are never called.
The real integrations are not part of this release."""

def read_document(*args, **kwargs):
    raise RuntimeError("read_document: stubbed in the research release; the harness never runs real tools")

def list_form_fields(*args, **kwargs):
    raise RuntimeError("list_form_fields: stubbed in the research release; the harness never runs real tools")

def fill_document(*args, **kwargs):
    raise RuntimeError("fill_document: stubbed in the research release; the harness never runs real tools")
