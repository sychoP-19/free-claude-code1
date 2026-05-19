import base64
import json
import logging
import os
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)

CREDENTIALS_PATH = Path.home() / ".config" / "free-claude-code" / "gmail_token.json"
CLIENT_SECRETS = {
    "client_id":     os.environ.get("GOOGLE_CLIENT_ID", ""),
    "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    "redirect_uri":  "http://localhost:8090/auth/gmail/callback",
    "scopes":        ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly"],
}


def _get_flow():
    from google_auth_oauthlib.flow import Flow
    return Flow.from_client_config(
        {
            "web": {
                "client_id":     CLIENT_SECRETS["client_id"],
                "client_secret": CLIENT_SECRETS["client_secret"],
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": [CLIENT_SECRETS["redirect_uri"]],
            }
        },
        scopes=CLIENT_SECRETS["scopes"],
        redirect_uri=CLIENT_SECRETS["redirect_uri"],
    )


def get_auth_url() -> str:
    if not CLIENT_SECRETS["client_id"]:
        raise RuntimeError("GOOGLE_CLIENT_ID not set in environment")
    flow = _get_flow()
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true")
    return url


def exchange_code(code: str) -> dict:
    flow = _get_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes) if creds.scopes else CLIENT_SECRETS["scopes"],
    }
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(json.dumps(token_data, indent=2))
    return token_data


def get_credentials():
    if not CREDENTIALS_PATH.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        data = json.loads(CREDENTIALS_PATH.read_text())
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id") or CLIENT_SECRETS["client_id"],
            client_secret=data.get("client_secret") or CLIENT_SECRETS["client_secret"],
            scopes=data.get("scopes", CLIENT_SECRETS["scopes"]),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            data["token"] = creds.token
            CREDENTIALS_PATH.write_text(json.dumps(data, indent=2))
        return creds
    except Exception as e:
        logger.error("Gmail credentials error: %s", e)
        return None


def get_user_email(creds) -> str:
    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress", "")
    except Exception:
        return ""


def is_connected() -> bool:
    creds = get_credentials()
    return creds is not None and creds.valid


def send_notification(subject: str, body: str) -> bool:
    creds = get_credentials()
    if not creds:
        logger.warning("Gmail not connected — skipping notification")
        return False
    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
        msg = MIMEText(body)
        msg["to"] = "me"
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info("Gmail notification sent: %s", subject)
        return True
    except Exception as e:
        logger.error("Gmail send failed: %s", e)
        return False
