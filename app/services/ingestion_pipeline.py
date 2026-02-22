"""
Email ingestion pipeline: fetch -> skip processed -> keyword filter -> regex extract -> store -> mark processed.
Uses BaseIngestionService (e.g. GmailIngestionService) so parsing and persistence are source-agnostic; SMS can plug in later.
Single DB transaction; per-email failures do not abort the run; batch lookup and batch insert; structured logging.

Scalability: To run in background (e.g. Celery), call run_ingestion_pipeline inside a task:
  # from app.services.ingestion_pipeline import run_ingestion_pipeline
  # @celery.task
  # def run_ingestion_async(user_id, after_date=None, max_emails=50):
  #     with app.app_context():
  #         return run_ingestion_pipeline(user_id=user_id, after_date=after_date, max_emails=max_emails)
"""
import logging
from datetime import datetime
from typing import Optional, Tuple, List

from flask import current_app

from .constants import RAW_TEXT_MAX_LENGTH, MAX_SMS_PER_RUN

logger = logging.getLogger(__name__)


def _log_ingestion(event: str, user_id: int, **kwargs) -> None:
    """Structured log for observability."""
    logger.info(
        "ingestion.%s user_id=%s %s",
        event,
        user_id,
        " ".join(f"{k}={v}" for k, v in sorted(kwargs.items())),
        extra={"event": event, "user_id": user_id, **kwargs},
    )


def run_ingestion_pipeline(
    user_id: int,
    after_date: Optional[datetime] = None,
    max_emails: int = 50,
    query: Optional[str] = None,
    ingestion_service=None,
) -> Tuple[int, int, Optional[str]]:
    """
    Run the full pipeline for the given user:
    1. Fetch messages via ingestion_service.fetch_messages (e.g. Gmail).
    2. Skip messages already in ProcessedEmail (single batch query).
    3. For each new message: filter (is_relevant) -> extract -> collect (one failure does not break run).
    4. Single transaction: batch insert IngestedTransaction + ProcessedEmail; update UserIngestionState.
    Returns (processed_count, new_transactions_count, error_message or None).
    """
    from .gmail_service import GmailIngestionService
    from .parser import is_relevant, extract_transaction_data
    from app.models import db, ProcessedEmail, IngestedTransaction, UserIngestionState

    app = current_app
    if not app:
        return 0, 0, "No app context"

    service = ingestion_service or GmailIngestionService(app, user_id, query=query)
    try:
        messages = service.fetch_messages(
            after_date=after_date, max_results=max_emails, query=query
        )
    except Exception as e:
        logger.exception("Fetch failed: %s", e)
        return 0, 0, str(e)

    fetch_count = len(messages)
    _log_ingestion("fetch", user_id, fetch_count=fetch_count)

    if not messages:
        return 0, 0, None

    # Batch lookup: all external message ids for this user that we already processed
    msg_ids = [m["id"] for m in messages if m.get("id")]
    if not msg_ids:
        return 0, 0, None
    existing = set(
        r[0]
        for r in ProcessedEmail.query.filter(
            ProcessedEmail.user_id == user_id,
            ProcessedEmail.gmail_message_id.in_(msg_ids),
        ).with_entities(ProcessedEmail.gmail_message_id).all()
    )

    to_process = [m for m in messages if m.get("id") and m["id"] not in existing]
    filter_pass_count = 0
    extraction_success_count = 0
    processed_records: List[ProcessedEmail] = []
    transaction_rows: List[IngestedTransaction] = []

    for msg in to_process:
        msg_id = msg.get("id")
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        try:
            if not is_relevant(text):
                continue
            filter_pass_count += 1
            data = extract_transaction_data(text)
            if not data:
                continue
            extraction_success_count += 1
            raw_safe = (text[:RAW_TEXT_MAX_LENGTH]) if text else None
            txn = IngestedTransaction(
                user_id=user_id,
                amount=data["amount"],
                transaction_type=data.get("transaction_type"),
                source="email",
                raw_text=raw_safe,
                extracted_date=data.get("extracted_date"),
            )
            transaction_rows.append(txn)
            processed_records.append(ProcessedEmail(gmail_message_id=msg_id, user_id=user_id))
        except Exception as e:
            logger.warning(
                "ingestion.parse_failed message_id=%s user_id=%s error=%s",
                msg_id, user_id, e,
                extra={"message_id": msg_id, "user_id": user_id, "error": str(e)},
            )

    _log_ingestion(
        "filter_pass", user_id,
        filter_pass_count=filter_pass_count,
        extraction_success_count=extraction_success_count,
    )

    try:
        db.session.add_all(transaction_rows)
        db.session.add_all(processed_records)
        now = datetime.utcnow()
        state = UserIngestionState.query.get(user_id)
        if state:
            state.last_ingested_at = now
            state.updated_at = now
        else:
            db.session.add(UserIngestionState(user_id=user_id, last_ingested_at=now, updated_at=now))
        db.session.commit()
        _log_ingestion(
            "commit", user_id,
            processed_count=len(processed_records),
            new_transactions=len(transaction_rows),
        )
        return len(processed_records), len(transaction_rows), None
    except Exception as e:
        db.session.rollback()
        logger.exception("ingestion.commit_failed user_id=%s error=%s", user_id, e)
        return 0, 0, str(e)


def run_sms_ingestion_pipeline(
    user_id: int,
    after_date: Optional[datetime] = None,
    max_messages: int = 100,
) -> Tuple[int, int, Optional[str]]:
    """
    Run SMS ingestion for the given user:
    1. Fetch from UploadedSMS via SMSIngestionService (optional after_date filter).
    2. Skip already processed (ProcessedSMS) via batch lookup.
    3. For each: is_relevant -> extract_transaction_data -> collect IngestedTransaction(source="sms") + ProcessedSMS.
    4. Single transaction commit; per-message try/except; rollback on commit failure.
    Returns (processed_count, new_transactions_count, error_message or None).
    """
    from .sms_service import SMSIngestionService
    from .parser import is_relevant, extract_transaction_data
    from app.models import db, ProcessedSMS, IngestedTransaction, UserIngestionState

    app = current_app
    if not app:
        return 0, 0, "No app context"

    max_messages = min(max(int(max_messages), 1), MAX_SMS_PER_RUN)
    service = SMSIngestionService(app, user_id)
    try:
        messages = service.fetch_messages(
            after_date=after_date, max_results=max_messages
        )
    except Exception as e:
        logger.exception("SMS fetch failed: %s", e)
        return 0, 0, str(e)

    fetch_count = len(messages)
    _log_ingestion("sms_fetch", user_id, fetch_count=fetch_count)

    if not messages:
        return 0, 0, None

    msg_ids = [m["id"] for m in messages if m.get("id")]
    if not msg_ids:
        return 0, 0, None

    existing = set(
        r[0]
        for r in ProcessedSMS.query.filter(
            ProcessedSMS.user_id == user_id,
            ProcessedSMS.device_sms_id.in_(msg_ids),
        ).with_entities(ProcessedSMS.device_sms_id).all()
    )

    to_process = [m for m in messages if m.get("id") and m["id"] not in existing]
    filter_pass_count = 0
    extraction_success_count = 0
    processed_records: List[ProcessedSMS] = []
    transaction_rows: List[IngestedTransaction] = []

    for msg in to_process:
        msg_id = msg.get("id")
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        try:
            if not is_relevant(text):
                continue
            filter_pass_count += 1
            data = extract_transaction_data(text)
            if not data:
                continue
            extraction_success_count += 1
            raw_safe = (text[:RAW_TEXT_MAX_LENGTH]) if text else None
            txn = IngestedTransaction(
                user_id=user_id,
                amount=data["amount"],
                transaction_type=data.get("transaction_type"),
                source="sms",
                raw_text=raw_safe,
                extracted_date=data.get("extracted_date"),
            )
            transaction_rows.append(txn)
            processed_records.append(ProcessedSMS(device_sms_id=msg_id, user_id=user_id))
        except Exception as e:
            logger.warning(
                "ingestion.sms_parse_failed device_sms_id=%s user_id=%s error=%s",
                msg_id, user_id, e,
                extra={"device_sms_id": msg_id, "user_id": user_id, "error": str(e)},
            )

    _log_ingestion(
        "sms_filter_pass", user_id,
        filter_pass_count=filter_pass_count,
        extraction_success_count=extraction_success_count,
    )

    try:
        db.session.add_all(transaction_rows)
        db.session.add_all(processed_records)
        now = datetime.utcnow()
        state = UserIngestionState.query.get(user_id)
        if state:
            state.last_ingested_at = now
            state.updated_at = now
        else:
            db.session.add(UserIngestionState(user_id=user_id, last_ingested_at=now, updated_at=now))
        db.session.commit()
        _log_ingestion(
            "sms_commit", user_id,
            processed_count=len(processed_records),
            new_transactions=len(transaction_rows),
        )
        return len(processed_records), len(transaction_rows), None
    except Exception as e:
        db.session.rollback()
        logger.exception("ingestion.sms_commit_failed user_id=%s error=%s", user_id, e)
        return 0, 0, str(e)
