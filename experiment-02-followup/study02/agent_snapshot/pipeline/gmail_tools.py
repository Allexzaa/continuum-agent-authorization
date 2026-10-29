"""Stub of the real integration module. The research harness replaces every tool call with a synthetic mock world, so these functions are never called.
The real integrations are not part of this release."""

def read_emails(*args, **kwargs):
    raise RuntimeError("read_emails: stubbed in the research release; the harness never runs real tools")

def read_email_body(*args, **kwargs):
    raise RuntimeError("read_email_body: stubbed in the research release; the harness never runs real tools")

def send_email(*args, **kwargs):
    raise RuntimeError("send_email: stubbed in the research release; the harness never runs real tools")

def reply_to_email(*args, **kwargs):
    raise RuntimeError("reply_to_email: stubbed in the research release; the harness never runs real tools")

def search_emails(*args, **kwargs):
    raise RuntimeError("search_emails: stubbed in the research release; the harness never runs real tools")

def forward_email(*args, **kwargs):
    raise RuntimeError("forward_email: stubbed in the research release; the harness never runs real tools")

def trash_email(*args, **kwargs):
    raise RuntimeError("trash_email: stubbed in the research release; the harness never runs real tools")

def trash_email_by_query(*args, **kwargs):
    raise RuntimeError("trash_email_by_query: stubbed in the research release; the harness never runs real tools")
