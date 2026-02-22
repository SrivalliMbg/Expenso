"""
Gmail API service layer. OAuth2 via stored tokens; fetch emails with search query and optional date filter.
No plain passwords; tokens from DB (encrypted). Uses gmail.readonly scope only.
GmailIngestionService implements BaseIngestionService for pipeline (source-agnostic fetch_messages).
"""
import logging
from typing import List, Optional
from datetime import datetime

from .constants import BODY_TEXT_MAX_LENGTH, MAX_EMAILS_PER_RUN
from .base_ingestion import BaseIngestionService

logger = logging.getLogger(__name__)

# Incremental sync: Gmail supports history.list(historyId=...) for changes since a point; store historyId
# per user (e.g. in UserIngestionState) and use it instead of full query for faster incremental runs.

# Default Gmail search query for transaction-related emails (pre-filter at API level)
DEFAULT_TRANSACTION_QUERY = (
    "subject:(invoice OR transaction OR credited OR debited OR payment OR order OR bank) "
    "OR body:(UPI OR payment OR order OR bank OR credited OR debited OR invoice)"
)


def _build_gmail_query(base_query: str, after_date: Optional[datetime]) -> str:
    """Append after:YYYY/MM/DD to query when provided."""
    if not after_date:
        return base_query
    try:
        date_str = after_date.strftime("%Y/%m/%d")
        return f"{base_query} after:{date_str}"
    except Exception:
        return base_query


def _get_credentials_for_user(user_id: int, app):
    """Build refreshable Credentials from stored tokens."""
    from google.oauth2.credentials import Credentials
    from app.gmail_oauth import get_oauth_tokens

    if not getattr(app, "mysql_pool", None):
        return None
    conn = app.mysql_pool.get_connection()
    try:
        access, refresh = get_oauth_tokens(user_id, conn, app)
        conn.close()
    except Exception as e:
        logger.exception("Failed to get OAuth tokens: %s", e)
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return None
    if not access:
        return None
    client_id = app.config.get("GOOGLE_CLIENT_ID")
    client_secret = app.config.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    return Credentials(
        token=access,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )


class GmailService:
    """
    Gmail API wrapper. Fetches messages using search query and optional after_date.
    Does not fetch entire inbox; uses list + get by id for only matching messages.
    """

    def __init__(self, app, user_id: int):
        self.app = app
        self.user_id = user_id
        self._service = None

    def _get_service(self):
        """Lazy-build Gmail API service; refresh token if needed."""
        if self._service is not None:
            return self._service
        creds = _get_credentials_for_user(self.user_id, self.app)
        if not creds:
            return None
        try:
            from googleapiclient.discovery import build
            from google.auth.transport.requests import Request
            if getattr(creds, "refresh_token", None):
                try:
                    creds.refresh(Request())
                except Exception:
                    pass
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            return self._service
        except Exception as e:
            logger.exception("Gmail build failed: %s", e)
            return None

    def fetch_emails(
        self,
        query: Optional[str] = None,
        after_date: Optional[datetime] = None,
        max_results: int = 50,
    ) -> List[dict]:
        """
        Fetch email metadata and body snippet for messages matching the query.
        Returns list of dicts: { "id", "thread_id", "snippet", "body_text", "subject" }.
        Body text is truncated to BODY_TEXT_MAX_LENGTH. max_results is capped at MAX_EMAILS_PER_RUN.
        Does NOT fetch entire inbox; uses Gmail search.
        """
        service = self._get_service()
        if not service:
            return []
        max_results = min(max(int(max_results), 1), MAX_EMAILS_PER_RUN)
        q = _build_gmail_query(query or DEFAULT_TRANSACTION_QUERY, after_date)
        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", q=q, maxResults=max_results)
                .execute()
            )
        except Exception as e:
            logger.exception("Gmail list failed: %s", e)
            return []
        messages = results.get("messages") or []
        out = []
        for msg_ref in messages:
            msg_id = msg_ref.get("id")
            if not msg_id:
                continue
            try:
                full = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
            except Exception as e:
                logger.warning("Gmail get message %s failed: %s", msg_id, e)
                continue
            payload = full.get("payload") or {}
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers") or []}
            subject = headers.get("subject", "")
            body_text = _extract_body_text(payload)
            if len(body_text) > BODY_TEXT_MAX_LENGTH:
                body_text = body_text[:BODY_TEXT_MAX_LENGTH]
            snippet = full.get("snippet", "")
            out.append({
                "id": msg_id,
                "thread_id": full.get("threadId", ""),
                "snippet": snippet,
                "body_text": body_text,
                "subject": subject,
            })
        return out


def _extract_body_text(payload: dict) -> str:
    """Extract plain text from message payload (multipart or single)."""
    import base64
    body = payload.get("body") or {}
    if body.get("data"):
        try:
            return base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="replace")
        except Exception:
            pass
    for part in payload.get("parts") or []:
        b = part.get("body") or {}
        if part.get("mimeType") == "text/plain" and b.get("data"):
            try:
                return base64.urlsafe_b64decode(b["data"]).decode("utf-8", errors="replace")
            except Exception:
                pass
    return ""


class GmailIngestionService(BaseIngestionService):
    """
    Gmail implementation of BaseIngestionService. Returns normalized messages
    { "id", "text" } for the pipeline (source-agnostic parsing/persistence).
    """

    def __init__(self, app, user_id: int, query: Optional[str] = None):
        super().__init__(app, user_id)
        self._gmail = GmailService(app, user_id)
        self._query = query

    def fetch_messages(
        self,
        after_date: Optional[datetime] = None,
        max_results: int = 50,
        **kwargs,
    ) -> List[dict]:
        query = kwargs.get("query") or self._query
        raw = self._gmail.fetch_emails(
            query=query, after_date=after_date, max_results=max_results
        )
        out = []
        for em in raw:
            msg_id = em.get("id")
            if not msg_id:
                continue
            text = f"{em.get('subject', '')} {em.get('snippet', '')} {em.get('body_text', '')}"
            if len(text) > BODY_TEXT_MAX_LENGTH:
                text = text[:BODY_TEXT_MAX_LENGTH]
            out.append({"id": msg_id, "text": text})
        return out
