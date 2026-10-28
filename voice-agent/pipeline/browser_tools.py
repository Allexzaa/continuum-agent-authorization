import time
import httpx

BRIDGE_URL = "http://127.0.0.1:8765"
_client = httpx.Client(timeout=30)


def _is_connected() -> bool:
    try:
        r = _client.get(f"{BRIDGE_URL}/health", timeout=3)
        return r.json().get("extension_connected", False)
    except Exception:
        return False


def _command(action: str, params: dict = {}) -> dict:
    r = _client.post(f"{BRIDGE_URL}/command", json={"action": action, "params": params})
    r.raise_for_status()
    result = r.json()
    return result.get("data") or result


def browser_query(action: str, params: dict = {}) -> str:
    if not _is_connected():
        return "Browser bridge is not connected. Make sure the bridge server is running and the Persia extension is loaded in Chromium."

    # These actions require a specific LinkedIn page — navigate there first.
    _nav_urls = {
        "get_inbox":         "https://www.linkedin.com/messaging/",
        "get_notifications": "https://www.linkedin.com/notifications/",
        "get_feed":          "https://www.linkedin.com/feed/",
    }
    if action in _nav_urls:
        try:
            _command("navigate_to", {"url": _nav_urls[action]})
        except Exception:
            pass
        time.sleep(5)

    try:
        data = _command(action, params)
    except Exception as e:
        err = str(e)
        if "429" in err or "CAPTCHA" in err:
            return "LinkedIn has shown a CAPTCHA or security check. Please open Chromium and solve it manually, then try again."
        return f"Browser bridge error: {e}"

    if not data:
        return "No data returned from browser."

    if data.get("captcha_detected"):
        return "LinkedIn is showing a security check or CAPTCHA in Chromium. Please solve it manually in the browser, then try again."

    # Handle search_jobs before the generic error check — extractor returns both
    # `error` and `jobs: []` when no cards are found (e.g. page still loading).
    if action == "search_jobs":
        jobs = data.get("jobs", [])
        if not jobs:
            return "No job listings found on the page yet. LinkedIn may still be rendering — please try the search again."
        lines = [f"Found {len(jobs)} job(s):\n"]
        for i, j in enumerate(jobs, 1):
            lines.append(f"{i}. {j.get('title', 'Unknown title')}")
            lines.append(f"   Company: {j.get('company', 'Unknown')}")
            lines.append(f"   Location: {j.get('location', 'Unknown')}")
            lines.append(f"   Job ID: {j.get('job_id', '')}")
            lines.append(f"   URL: {j.get('url', '').split('?')[0]}")
        return "\n".join(lines)

    if data.get("error"):
        return f"Browser action failed: {data['error']}"

    if action == "get_job_details":
        title = data.get("title", "")
        company = data.get("company", "")
        location = data.get("location", "")
        desc = data.get("description", "")
        return (
            f"Job: {title}\nCompany: {company}\nLocation: {location}\n\n"
            f"Description:\n{desc}"
        )

    if action == "get_profile":
        return (
            f"Name: {data.get('name', '')}\n"
            f"Headline: {data.get('headline', '')}\n"
            f"Location: {data.get('location', '')}\n"
            f"About: {data.get('about', '')}\n"
            f"Recent roles: {', '.join(data.get('recent_roles', []))}"
        )

    if action == "get_feed":
        posts = data.get("posts", [])
        if not posts:
            return "No feed posts found."
        lines = [f"LinkedIn feed — {len(posts)} post(s):\n"]
        for i, p in enumerate(posts, 1):
            lines.append(f"{i}. {p.get('author', 'Unknown')} ({p.get('timestamp', '')})")
            lines.append(f"   {p.get('content', '')[:300]}")
        return "\n".join(lines)

    if action == "get_notifications":
        items = data.get("notifications", [])
        if not items:
            return "No notifications found."
        lines = [f"{i+1}. {n['text']}" for i, n in enumerate(items)]
        return "LinkedIn notifications:\n" + "\n".join(lines)

    if action == "get_inbox":
        convos = data.get("conversations", [])
        raw = data.get("raw_text", "")
        if not convos:
            if raw:
                return f"LinkedIn inbox (raw preview):\n{raw[:1500]}"
            return "No conversations found in LinkedIn inbox. Make sure you're logged in to LinkedIn."
        lines = [f"LinkedIn inbox — {len(convos)} conversation(s):\n"]
        for i, c in enumerate(convos, 1):
            unread = " [UNREAD]" if c.get("unread") else ""
            lines.append(f"{i}. {c.get('name', 'Unknown')}{unread}")
            if c.get("preview"):
                lines.append(f"   {c['preview'][:150]}")
            if c.get("timestamp"):
                lines.append(f"   {c['timestamp']}")
        return "\n".join(lines)

    if action == "navigate_to":
        # If the extension hasn't yet applied the page-load wait (background.js),
        # sleep here so LinkedIn's React SPA has time to render before search_jobs.
        nav_url = (params.get("url") or data.get("url") or "").lower()
        if "linkedin.com" in nav_url:
            time.sleep(5)
        return f"Navigated to: {data.get('url', '')}"

    if action == "get_page_text":
        return data.get("text", "")

    # Fallback — return raw JSON summary
    return str(data)[:2000]
