import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import caldav
import requests as _requests
from caldav.elements import dav
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from icalendar import Calendar, Event as ICalEvent

# ── Shared config ─────────────────────────────────────────────────────────────
_TZ = ZoneInfo(os.getenv("CALENDAR_TIMEZONE", "America/Los_Angeles"))

# ── Apple CalDAV ──────────────────────────────────────────────────────────────
CALDAV_URL = "https://caldav.icloud.com"
_APPLE_USER = os.getenv("APPLE_CALENDAR_USER", "")
_APPLE_PASS = os.getenv("APPLE_CALENDAR_PASSWORD", "")
_CAL_NAME   = os.getenv("APPLE_CALENDAR_NAME", "")

# ── Google Calendar ───────────────────────────────────────────────────────────
_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]
_TOKEN_FILE = Path(__file__).parent.parent / "config" / "google_token.json"


# ── Apple helpers ─────────────────────────────────────────────────────────────

def _apple_available() -> bool:
    return bool(_APPLE_USER and _APPLE_PASS)


def _get_apple_calendars(retries: int = 3, delay: float = 2.0):
    last_exc = None
    for attempt in range(retries):
        try:
            client = caldav.DAVClient(
                url=CALDAV_URL, username=_APPLE_USER, password=_APPLE_PASS,
                timeout=15,
            )
            principal = client.principal()
            all_cals = principal.calendars()
            if _CAL_NAME:
                for cal in all_cals:
                    props = cal.get_properties([dav.DisplayName()])
                    if props.get("{DAV:}displayname", "").lower() == _CAL_NAME.lower():
                        return [cal], client
                return [], client
            skip = {"reminders ⚠️", "tasks", "reminders"}
            result = [
                cal for cal in all_cals
                if cal.get_properties([dav.DisplayName()]).get("{DAV:}displayname", "").lower() not in skip
            ]
            return result, client
        except Exception as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(delay)
    raise last_exc


def _find_apple_event_url(event_id: str) -> str | None:
    calendars, _ = _get_apple_calendars()
    start = datetime(2020, 1, 1, tzinfo=_TZ)
    end   = datetime(2030, 12, 31, tzinfo=_TZ)
    for cal in calendars:
        try:
            events = cal.search(start=start, end=end, event=True, expand=False)
        except Exception:
            continue
        for e in events:
            ical = Calendar.from_ical(e.data)
            for component in ical.walk():
                if component.name == "VEVENT" and str(component.get("UID", "")) == event_id:
                    return str(e.url)
    return None


# ── Google helpers ────────────────────────────────────────────────────────────

def _google_available() -> bool:
    return _TOKEN_FILE.exists()


def _get_google_service():
    creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _GOOGLE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _TOKEN_FILE.write_text(creds.to_json())
    return build("calendar", "v3", credentials=creds)


# ── Public tools ──────────────────────────────────────────────────────────────

def get_calendar_events(time_min: str, time_max: str, max_results: int = 10) -> str:
    """Return events from Apple and Google calendars combined."""
    lines = []
    start = datetime.fromisoformat(time_min).astimezone(_TZ)
    end   = datetime.fromisoformat(time_max).astimezone(_TZ)

    # Apple
    if _apple_available():
        try:
            calendars, _ = _get_apple_calendars()
            for cal in calendars:
                events = None
                for attempt in range(3):
                    try:
                        events = cal.search(start=start, end=end, event=True, expand=True)
                        break
                    except Exception:
                        if attempt < 2:
                            time.sleep(2)
                if events is None:
                    continue
                for e in events:
                    ical = Calendar.from_ical(e.data)
                    for component in ical.walk():
                        if component.name == "VEVENT":
                            summary = str(component.get("SUMMARY", "(no title)"))
                            dtstart = component.get("DTSTART")
                            if dtstart:
                                dt = dtstart.dt
                                if hasattr(dt, "hour"):
                                    start_str = dt.astimezone(_TZ).strftime("%Y-%m-%d %H:%M %Z")
                                else:
                                    start_str = dt.isoformat() + " (all day)"
                            else:
                                start_str = "?"
                            uid = str(component.get("UID", ""))
                            lines.append(f"- [Apple] {summary} | {start_str} | ID: {uid}")
        except Exception as e:
            lines.append(f"- [Apple] Error: {e}")

    # Google
    if _google_available():
        try:
            service = _get_google_service()
            result = service.events().list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            for e in result.get("items", []):
                summary = e.get("summary", "(no title)")
                start_raw = e["start"].get("dateTime", e["start"].get("date", ""))
                if "T" in start_raw:
                    start_str = datetime.fromisoformat(start_raw).astimezone(_TZ).strftime("%Y-%m-%d %H:%M %Z")
                else:
                    start_str = start_raw + " (all day)"
                lines.append(f"- [Google] {summary} | {start_str} | ID: {e['id']}")
        except Exception as e:
            lines.append(f"- [Google] Error: {e}")

    if not lines:
        return "No events found in that time range."
    return "\n".join(lines[:max_results])


_RRULE_MAP = {
    "daily":    "RRULE:FREQ=DAILY",
    "weekly":   "RRULE:FREQ=WEEKLY",
    "biweekly": "RRULE:FREQ=WEEKLY;INTERVAL=2",
    "monthly":  "RRULE:FREQ=MONTHLY",
    "yearly":   "RRULE:FREQ=YEARLY",
    "weekdays": "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
}


def create_calendar_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    source: str = "apple",
    recurrence: str = "",
) -> str:
    """Create a calendar event. source='apple' or 'google'.
    recurrence: '', 'daily', 'weekly', 'biweekly', 'monthly', 'yearly', 'weekdays'
    """
    dtstart = datetime.fromisoformat(start).astimezone(_TZ)
    dtend   = datetime.fromisoformat(end).astimezone(_TZ)
    rrule   = _RRULE_MAP.get(recurrence.lower().strip(), "") if recurrence else ""
    recur_label = f" (repeating {recurrence})" if rrule else ""

    if source.lower() == "google" and _google_available():
        try:
            service = _get_google_service()
            event = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": dtstart.isoformat(), "timeZone": str(_TZ)},
                "end":   {"dateTime": dtend.isoformat(),   "timeZone": str(_TZ)},
            }
            if rrule:
                event["recurrence"] = [rrule]
            service.events().insert(calendarId="primary", body=event).execute()
            return f"Event created in Google Calendar: {summary} on {dtstart.strftime('%Y-%m-%d at %H:%M')}{recur_label}."
        except Exception as e:
            return f"Google Calendar error: {e}"

    # Default: Apple
    if not _apple_available():
        return "Apple Calendar credentials not set."
    try:
        from icalendar import vRecur
        calendars, _ = _get_apple_calendars()
        cal = calendars[0]
        event = ICalEvent()
        event.add("summary", summary)
        event.add("dtstart", dtstart)
        event.add("dtend", dtend)
        if description:
            event.add("description", description)
        if rrule:
            # Parse RRULE string into vRecur for icalendar library
            rrule_value = rrule.replace("RRULE:", "")
            parts = dict(p.split("=") for p in rrule_value.split(";"))
            event.add("rrule", parts)
        ical = Calendar()
        ical.add("prodid", "-//Persia//EN")
        ical.add("version", "2.0")
        ical.add_component(event)
        cal.save_event(ical.to_ical().decode())
        return f"Event created in Apple Calendar: {summary} on {dtstart.strftime('%Y-%m-%d at %H:%M')}{recur_label}."
    except Exception as e:
        return f"Apple Calendar error: {e}"


def update_calendar_event(event_id: str, summary: str = None, start: str = None, end: str = None, description: str = None) -> str:
    """Update an event — tries Apple first, then Google."""
    # Try Apple
    if _apple_available():
        event_url = _find_apple_event_url(event_id)
        if event_url:
            try:
                auth = (_APPLE_USER, _APPLE_PASS)
                get_resp = _requests.get(event_url, auth=auth)
                etag = get_resp.headers.get("ETag", "*")
                ical = Calendar.from_ical(get_resp.text)
                for component in ical.walk():
                    if component.name == "VEVENT":
                        if summary:     component["SUMMARY"] = summary
                        if description is not None: component["DESCRIPTION"] = description
                        if start: component["DTSTART"].dt = datetime.fromisoformat(start).astimezone(_TZ)
                        if end:   component["DTEND"].dt   = datetime.fromisoformat(end).astimezone(_TZ)
                put_resp = _requests.put(
                    event_url, auth=auth,
                    headers={"If-Match": etag, "Content-Type": "text/calendar"},
                    data=ical.to_ical(),
                )
                if put_resp.status_code in (200, 201, 204):
                    return "Event updated in Apple Calendar."
            except Exception as e:
                return f"Apple Calendar error: {e}"

    # Try Google
    if _google_available():
        try:
            service = _get_google_service()
            event = service.events().get(calendarId="primary", eventId=event_id).execute()
            if summary:     event["summary"] = summary
            if description is not None: event["description"] = description
            if start: event["start"] = {"dateTime": datetime.fromisoformat(start).astimezone(_TZ).isoformat(), "timeZone": str(_TZ)}
            if end:   event["end"]   = {"dateTime": datetime.fromisoformat(end).astimezone(_TZ).isoformat(),   "timeZone": str(_TZ)}
            service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
            return "Event updated in Google Calendar."
        except Exception as e:
            return f"Google Calendar error: {e}"

    return f"No event found with ID {event_id}."


def delete_calendar_event(event_id: str) -> str:
    """Delete an event — tries Apple first, then Google."""
    # Try Apple
    if _apple_available():
        event_url = _find_apple_event_url(event_id)
        if event_url:
            try:
                auth = (_APPLE_USER, _APPLE_PASS)
                get_resp = _requests.get(event_url, auth=auth)
                etag = get_resp.headers.get("ETag", "*")
                del_resp = _requests.delete(event_url, auth=auth, headers={"If-Match": etag})
                if del_resp.status_code in (200, 204):
                    return "Event deleted from Apple Calendar."
            except Exception as e:
                return f"Apple Calendar error: {e}"

    # Try Google
    if _google_available():
        try:
            service = _get_google_service()
            service.events().delete(calendarId="primary", eventId=event_id).execute()
            return "Event deleted from Google Calendar."
        except Exception as e:
            return f"Google Calendar error: {e}"

    return f"No event found with ID {event_id}."
