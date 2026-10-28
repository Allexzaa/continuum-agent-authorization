"""Stub of the real integration module. The research harness replaces every tool call with a synthetic mock world, so these functions are never called.
The real integrations are not part of this release."""

def list_slack_channels(*args, **kwargs):
    raise RuntimeError("list_slack_channels: stubbed in the research release; the harness never runs real tools")

def read_slack_channel(*args, **kwargs):
    raise RuntimeError("read_slack_channel: stubbed in the research release; the harness never runs real tools")

def read_slack_thread(*args, **kwargs):
    raise RuntimeError("read_slack_thread: stubbed in the research release; the harness never runs real tools")

def search_slack(*args, **kwargs):
    raise RuntimeError("search_slack: stubbed in the research release; the harness never runs real tools")

def get_slack_dm_history(*args, **kwargs):
    raise RuntimeError("get_slack_dm_history: stubbed in the research release; the harness never runs real tools")

def post_slack_message(*args, **kwargs):
    raise RuntimeError("post_slack_message: stubbed in the research release; the harness never runs real tools")

def reply_to_slack_thread(*args, **kwargs):
    raise RuntimeError("reply_to_slack_thread: stubbed in the research release; the harness never runs real tools")
