"""Stub of the real integration module. The research harness replaces every tool call with a synthetic mock world, so these functions are never called.
The real integrations are not part of this release."""

def run_command(*args, **kwargs):
    raise RuntimeError("run_command: stubbed in the research release; the harness never runs real tools")

def glob_files(*args, **kwargs):
    raise RuntimeError("glob_files: stubbed in the research release; the harness never runs real tools")

def grep_files(*args, **kwargs):
    raise RuntimeError("grep_files: stubbed in the research release; the harness never runs real tools")
