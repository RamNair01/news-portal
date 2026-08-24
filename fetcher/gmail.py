"""Gmail fetcher — pulls the latest Rundown AI newsletter via Gmail API."""

import base64
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from db.store import insert_item

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _get_credentials(credentials_file: str, token_file: str) -> Credentials:
    creds = None
    token_path = Path(token_file)
    creds_path = Path(credentials_file)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            logger.info("Stored Gmail authorization is invalid; requesting authorization again.")
            creds = None

    if not creds or not creds.valid:
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Gmail credentials file not found: {credentials_file}\n"
                "Download it from Google Cloud Console → APIs & Services → Credentials."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return creds


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _decode_body(payload: dict) -> str:
    """Recursively extract text from a Gmail message payload."""
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
    if mime == "text/html" and body_data:
        return _strip_html(base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace"))

    for part in payload.get("parts", []):
        result = _decode_body(part)
        if result:
            return result
    return ""


def fetch_gmail(config: dict) -> int | None:
    gmail_cfg = config.get("gmail", {})
    credentials_file = gmail_cfg.get("credentials_file", "credentials.json")
    token_file = gmail_cfg.get("token_file", "token.json")
    sender_filter = gmail_cfg.get("sender_filter", "newsletter@therundown.ai")

    try:
        creds = _get_credentials(credentials_file, token_file)
        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(
            userId="me",
            q=f"from:{sender_filter} is:unread",
            maxResults=1,
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            logger.info("No new Rundown AI emails found.")
            return 0

        msg_id = messages[0]["id"]
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        subject = headers.get("Subject", "The Rundown AI")
        date_str = headers.get("Date", "")
        guid = f"gmail:{msg_id}"

        body = _decode_body(msg["payload"])

        try:
            from email.utils import parsedate_to_datetime
            published_at = parsedate_to_datetime(date_str).astimezone(timezone.utc).isoformat()
        except Exception:
            published_at = datetime.now(timezone.utc).isoformat()

        inserted = insert_item(
            category="rundown",
            source="The Rundown AI",
            title=subject,
            url="",
            guid=guid,
            body=body,
            published_at=published_at,
        )

        if inserted:
            logger.info("Fetched Rundown AI newsletter: %s", subject)
            return 1
        else:
            logger.info("Rundown AI newsletter already in DB.")
            return 0

    except FileNotFoundError as exc:
        logger.error("Gmail setup error: %s", exc)
        return None
    except Exception as exc:
        logger.error("Gmail fetch failed: %s", exc)
        return None
