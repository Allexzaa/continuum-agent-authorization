"""Slack read tools — Phase 3.

5 read tools: list_slack_channels, read_slack_channel, read_slack_thread,
search_slack, get_slack_dm_history.

search_slack uses SLACK_USER_TOKEN (search:read scope — bot token not allowed).
All other tools use SLACK_BOT_TOKEN.
"""

import os
import re
import time
from datetime import datetime, timedelta, timezone

from dateutil import parser as dateutil_parser
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_BOT_TOKEN  = os.getenv("SLACK_BOT_TOKEN", "")
_USER_TOKEN = os.getenv("SLACK_USER_TOKEN", "")
_ALLOWED_USER_ID = os.getenv("SLACK_ALLOWED_USER_ID", "")

_bot_client  = WebClient(token=_BOT_TOKEN)
_user_client = WebClient(token=_USER_TOKEN)

_user_cache:    dict[str, str] = {}   # user_id → display name
_channel_cache: dict[str, str] = {}   # channel name (lower) → channel ID


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_user(user_id: str) -> str:
    if user_id in _user_cache:
        return _user_cache[user_id]
    try:
        resp = _bot_client.users_info(user=user_id)
        name = resp["user"].get("display_name") or resp["user"].get("real_name") or user_id
        _user_cache[user_id] = name
        return name
    except SlackApiError:
        return user_id


def _resolve_channel(name_or_id: str) -> str:
    """Return a Slack channel ID. Accepts '#engineering', 'engineering', or 'C0XXXXXXX'."""
    raw = name_or_id.lstrip("#").strip()
    # Already a channel ID
    if re.match(r"^[A-Z0-9]{9,11}$", raw):
        return raw
    key = raw.lower()
    if key in _channel_cache:
        return _channel_cache[key]
    try:
        cursor = None
        while True:
            kwargs = {"types": "public_channel,private_channel", "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            resp = _bot_client.conversations_list(**kwargs)
            for ch in resp.get("channels", []):
                _channel_cache[ch["name"].lower()] = ch["id"]
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError as e:
        raise RuntimeError(f"Could not list Slack channels: {e.response['error']}") from e
    if key not in _channel_cache:
        raise RuntimeError(f"Channel '{name_or_id}' not found or bot not invited.")
    return _channel_cache[key]


def _strip_mrkdwn(text: str) -> str:
    """Strip Slack mrkdwn formatting to plain text."""
    text = re.sub(r"<@([A-Z0-9]+)>", lambda m: f"@{_resolve_user(m.group(1))}", text)
    text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)
    text = re.sub(r"<([^|>]+)\|([^>]+)>", r"\2", text)   # link with label
    text = re.sub(r"<([^>]+)>", r"\1", text)              # bare URL
    text = re.sub(r"\*([^*]+)\*", r"\1", text)            # bold
    text = re.sub(r"_([^_]+)_", r"\1", text)              # italic
    text = re.sub(r"`([^`]+)`", r"\1", text)              # inline code
    return text.strip()


def _format_messages(messages: list, indent: str = "") -> str:
    lines = []
    for msg in messages:
        ts_float = float(msg.get("ts", 0))
        dt = datetime.fromtimestamp(ts_float, tz=timezone.utc).strftime("%H:%M")
        user = _resolve_user(msg.get("user", "")) if msg.get("user") else "bot"
        text = _strip_mrkdwn(msg.get("text", ""))
        if text:
            lines.append(f"{indent}[{dt}] @{user}: {text}")
    result = "\n".join(lines)
    if len(result) > 2000:
        result = result[:1997] + "..."
    return result or "(no messages)"


def _parse_since(since_str: str) -> float:
    """Natural language or ISO date → Unix timestamp (UTC). Returns 0.0 if None/empty."""
    if not since_str:
        return 0.0
    now = datetime.now(tz=timezone.utc)
    s = since_str.lower().strip()
    if s in ("today",):
        return now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    if s in ("yesterday",):
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    if s in ("this week",):
        return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    m = re.match(r"last\s+(\d+)\s+days?", s)
    if m:
        return (now - timedelta(days=int(m.group(1)))).timestamp()
    try:
        dt = dateutil_parser.parse(since_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def list_slack_channels() -> str:
    """Return a plain-text list of all Slack channels the bot can see."""
    try:
        names = []
        cursor = None
        while True:
            kwargs = {"types": "public_channel,private_channel", "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            resp = _bot_client.conversations_list(**kwargs)
            for ch in resp.get("channels", []):
                _channel_cache[ch["name"].lower()] = ch["id"]
                prefix = "#" if not ch.get("is_private") else "🔒"
                names.append(f"{prefix}{ch['name']}")
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        if not names:
            return "No channels found. Make sure @Persia has been invited to at least one channel."
        return "\n".join(sorted(names))
    except SlackApiError as e:
        return f"Slack error: {e.response['error']}"


def read_slack_channel(channel: str, limit: int = 20, since: str = "") -> str:
    """Read recent messages from a Slack channel."""
    try:
        channel_id = _resolve_channel(channel)
    except RuntimeError as e:
        return str(e)
    try:
        oldest = _parse_since(since)
        kwargs: dict = {"channel": channel_id, "limit": min(limit, 100)}
        if oldest:
            kwargs["oldest"] = str(oldest)
        resp = _bot_client.conversations_history(**kwargs)
        messages = list(reversed(resp.get("messages", [])))
        if not messages:
            return f"No messages found in #{channel.lstrip('#')}" + (f" since {since}" if since else "") + "."
        return f"#{channel.lstrip('#')} — last {len(messages)} messages:\n" + _format_messages(messages)
    except SlackApiError as e:
        err = e.response["error"]
        if err == "not_in_channel":
            return f"Persia is not in #{channel.lstrip('#')}. Run /invite @Persia in that channel first."
        return f"Slack error: {err}"


def read_slack_thread(channel: str, thread_ts: str) -> str:
    """Read all replies in a Slack thread."""
    try:
        channel_id = _resolve_channel(channel)
    except RuntimeError as e:
        return str(e)
    try:
        resp = _bot_client.conversations_replies(channel=channel_id, ts=thread_ts)
        messages = resp.get("messages", [])
        if not messages:
            return "Thread not found or empty."
        root = messages[0]
        replies = messages[1:]
        result = "Thread root:\n" + _format_messages([root])
        if replies:
            result += f"\n\n{len(replies)} repl{'y' if len(replies)==1 else 'ies'}:\n"
            result += _format_messages(replies, indent="  ↳ ")
        return result
    except SlackApiError as e:
        err = e.response["error"]
        if err == "not_in_channel":
            return f"Persia is not in #{channel.lstrip('#')}. Run /invite @Persia in that channel first."
        return f"Slack error: {err}"


def search_slack(query: str, limit: int = 10) -> str:
    """Search Slack messages across the workspace. Uses user token (search:read scope)."""
    if not _USER_TOKEN:
        return "SLACK_USER_TOKEN is not set in .env. Add it to enable Slack search."
    try:
        resp = _user_client.search_messages(query=query, count=min(limit, 20))
        matches = resp.get("messages", {}).get("matches", [])
        if not matches:
            return f"No results found for: {query}"
        lines = [f"Search results for '{query}' ({len(matches)} found):"]
        for m in matches:
            channel_name = m.get("channel", {}).get("name", "unknown")
            ts_float = float(m.get("ts", 0))
            dt = datetime.fromtimestamp(ts_float, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            user = _resolve_user(m.get("user", "")) if m.get("user") else "bot"
            text = _strip_mrkdwn(m.get("text", ""))[:200]
            lines.append(f"  #{channel_name} [{dt}] @{user}: {text}")
        return "\n".join(lines)
    except SlackApiError as e:
        err = e.response["error"]
        if err == "not_allowed_token_type":
            return "search_slack requires a user token with search:read scope. Check SLACK_USER_TOKEN in .env."
        return f"Slack error: {err}"


def get_slack_dm_history(limit: int = 20) -> str:
    """Read recent messages from your DM conversation with Persia."""
    if not _ALLOWED_USER_ID:
        return "SLACK_ALLOWED_USER_ID is not set in .env."
    try:
        resp = _bot_client.conversations_open(users=[_ALLOWED_USER_ID])
        dm_channel = resp["channel"]["id"]
        hist = _bot_client.conversations_history(channel=dm_channel, limit=min(limit, 100))
        messages = list(reversed(hist.get("messages", [])))
        if not messages:
            return "No DM history found."
        return f"DM history — last {len(messages)} messages:\n" + _format_messages(messages)
    except SlackApiError as e:
        err = e.response["error"]
        if err == "missing_scope":
            return ("get_slack_dm_history requires additional scopes: im:history and im:write. "
                    "Add them under Bot Token Scopes in your Slack App settings, then reinstall the app.")
        return f"Slack error: {err}"


def post_slack_message(channel: str, text: str) -> str:
    """Post a message to a Slack channel on your behalf. Confirmation required."""
    try:
        channel_id = _resolve_channel(channel)
    except RuntimeError as e:
        return str(e)
    try:
        _bot_client.chat_postMessage(channel=channel_id, text=text)
        return f"Message posted to #{channel.lstrip('#')}."
    except SlackApiError as e:
        err = e.response["error"]
        if err == "not_in_channel":
            return f"Persia is not in #{channel.lstrip('#')}. Run /invite @Persia in that channel first."
        return f"Slack error: {err}"


def reply_to_slack_thread(channel: str, thread_ts: str, text: str) -> str:
    """Reply to a Slack thread. Confirmation required."""
    try:
        channel_id = _resolve_channel(channel)
    except RuntimeError as e:
        return str(e)
    try:
        _bot_client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=text)
        return f"Reply posted to thread in #{channel.lstrip('#')}."
    except SlackApiError as e:
        err = e.response["error"]
        if err == "not_in_channel":
            return f"Persia is not in #{channel.lstrip('#')}. Run /invite @Persia in that channel first."
        return f"Slack error: {err}"
