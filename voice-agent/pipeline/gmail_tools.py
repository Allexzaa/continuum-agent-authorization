import base64
import email as _email
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]
_TOKEN_FILE = Path(__file__).parent.parent / "config" / "google_token.json"


def _gmail_available() -> bool:
    return _TOKEN_FILE.exists()


def _get_gmail_service():
    creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: dict) -> str:
    """Recursively extract plain text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")

    if mime_type == "text/html" and body_data:
        # Fallback: strip tags minimally so it's somewhat readable
        raw = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        import re
        return re.sub(r"<[^>]+>", " ", raw).strip()

    for part in payload.get("parts", []):
        text = _decode_body(part)
        if text:
            return text

    return ""


def _header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def read_emails(max_results: int = 10, label: str = "INBOX") -> str:
    """List recent emails — returns sender, subject, date, and message ID."""
    if not _gmail_available():
        return "Gmail not authorized. Run scripts/auth_google.py to set up access."
    try:
        service = _get_gmail_service()
        result = service.users().messages().list(
            userId="me",
            labelIds=[label.upper()],
            maxResults=max_results,
        ).execute()
        messages = result.get("messages", [])
        if not messages:
            return f"No messages found in {label}."
        lines = []
        for m in messages:
            msg = service.users().messages().get(userId="me", id=m["id"], format="metadata",
                                                  metadataHeaders=["From", "Subject", "Date"]).execute()
            headers = msg.get("payload", {}).get("headers", [])
            sender = _header(headers, "From")
            subject = _header(headers, "Subject") or "(no subject)"
            date = _header(headers, "Date")
            lines.append(f"- ID: {m['id']} | From: {sender} | Subject: {subject} | Date: {date}")
        return "\n".join(lines)
    except Exception as e:
        return f"Gmail error: {e}"


def read_email_body(message_id: str) -> str:
    """Read the full body of an email by its message ID."""
    if not _gmail_available():
        return "Gmail not authorized. Run scripts/auth_google.py to set up access."
    try:
        service = _get_gmail_service()
        msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        sender = _header(headers, "From")
        subject = _header(headers, "Subject") or "(no subject)"
        date = _header(headers, "Date")
        body = _decode_body(msg.get("payload", {}))
        if not body.strip():
            body = "(no readable body)"
        return f"From: {sender}\nSubject: {subject}\nDate: {date}\n\n{body[:3000]}"
    except Exception as e:
        return f"Gmail error: {e}"


def send_email(to: str, subject: str, body: str) -> str:
    """Send a new email."""
    if not _gmail_available():
        return "Gmail not authorized. Run scripts/auth_google.py to set up access."
    try:
        service = _get_gmail_service()
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {to} with subject '{subject}'."
    except Exception as e:
        return f"Gmail error: {e}"


def reply_to_email(message_id: str, body: str) -> str:
    """Reply to an existing email thread."""
    if not _gmail_available():
        return "Gmail not authorized. Run scripts/auth_google.py to set up access."
    try:
        service = _get_gmail_service()
        orig = service.users().messages().get(userId="me", id=message_id, format="metadata",
                                               metadataHeaders=["From", "Subject", "Message-ID",
                                                                 "References", "In-Reply-To"]).execute()
        headers = orig.get("payload", {}).get("headers", [])
        thread_id = orig.get("threadId", "")
        to = _header(headers, "From")
        orig_subject = _header(headers, "Subject") or ""
        subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"
        orig_msg_id = _header(headers, "Message-ID")
        references = _header(headers, "References")
        full_references = f"{references} {orig_msg_id}".strip() if references else orig_msg_id

        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        if orig_msg_id:
            msg["In-Reply-To"] = orig_msg_id
        if full_references:
            msg["References"] = full_references

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id},
        ).execute()
        return f"Reply sent to {to}."
    except Exception as e:
        return f"Gmail error: {e}"


def forward_email(message_id: str, to: str, note: str = "") -> str:
    """Forward an existing email to another address, with an optional note prepended."""
    if not _gmail_available():
        return "Gmail not authorized. Run scripts/auth_google.py to set up access."
    try:
        service = _get_gmail_service()
        orig = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = orig.get("payload", {}).get("headers", [])
        orig_subject = _header(headers, "Subject") or ""
        orig_from = _header(headers, "From")
        orig_date = _header(headers, "Date")
        orig_body = _decode_body(orig.get("payload", {}))

        subject = orig_subject if orig_subject.lower().startswith("fwd:") else f"Fwd: {orig_subject}"
        forwarded_block = (
            f"\n\n---------- Forwarded message ----------\n"
            f"From: {orig_from}\n"
            f"Date: {orig_date}\n"
            f"Subject: {orig_subject}\n\n"
            f"{orig_body[:3000]}"
        )
        full_body = (f"{note}\n{forwarded_block}") if note else forwarded_block

        msg = MIMEText(full_body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email forwarded to {to} with subject '{subject}'."
    except Exception as e:
        return f"Gmail error: {e}"


def trash_email(message_id: str) -> str:
    """Move an email to the trash by its message ID."""
    if not _gmail_available():
        return "Gmail not authorized. Run scripts/auth_google.py to set up access."
    try:
        service = _get_gmail_service()
        service.users().messages().trash(userId="me", id=message_id).execute()
        return f"Email {message_id} moved to trash."
    except Exception as e:
        return f"Gmail error: {e}"


def trash_email_by_query(query: str) -> str:
    """Search for an email by description and move it to trash. Use this instead of trash_email
    when you know what the email is about but not its exact ID."""
    if not _gmail_available():
        return "Gmail not authorized. Run scripts/auth_google.py to set up access."
    try:
        service = _get_gmail_service()
        result = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
        messages = result.get("messages", [])
        if not messages:
            return f"No emails found matching '{query}'."
        if len(messages) > 3:
            lines = []
            for m in messages[:5]:
                msg = service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                headers = msg.get("payload", {}).get("headers", [])
                lines.append(
                    f"- ID: {m['id']} | From: {_header(headers, 'From')} "
                    f"| Subject: {_header(headers, 'Subject')}"
                )
            return (
                f"Found {len(messages)} emails matching '{query}' — be more specific, or use trash_email "
                f"with one of these IDs:\n" + "\n".join(lines)
            )
        # One or two matches — trash the first (most relevant per Gmail ranking)
        msg_id = messages[0]["id"]
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="metadata",
            metadataHeaders=["From", "Subject"],
        ).execute()
        headers = msg.get("payload", {}).get("headers", [])
        subject = _header(headers, "Subject") or "(no subject)"
        sender = _header(headers, "From")
        service.users().messages().trash(userId="me", id=msg_id).execute()
        return f"Moved to trash: '{subject}' from {sender}."
    except Exception as e:
        return f"Gmail error: {e}"


def search_emails(query: str, max_results: int = 10) -> str:
    """Search emails using Gmail query syntax (e.g. 'from:alex subject:meeting')."""
    if not _gmail_available():
        return "Gmail not authorized. Run scripts/auth_google.py to set up access."
    try:
        service = _get_gmail_service()
        result = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
        ).execute()
        messages = result.get("messages", [])
        if not messages:
            return f"No messages found matching '{query}'."
        lines = []
        for m in messages:
            msg = service.users().messages().get(userId="me", id=m["id"], format="metadata",
                                                  metadataHeaders=["From", "Subject", "Date"]).execute()
            headers = msg.get("payload", {}).get("headers", [])
            sender = _header(headers, "From")
            subject = _header(headers, "Subject") or "(no subject)"
            date = _header(headers, "Date")
            lines.append(f"- ID: {m['id']} | From: {sender} | Subject: {subject} | Date: {date}")
        return "\n".join(lines)
    except Exception as e:
        return f"Gmail error: {e}"
