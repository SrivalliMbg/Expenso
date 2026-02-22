"""
Routes for email ingestion. Manual trigger and optional list of ingested transactions.
Security: gmail.readonly; token storage separate; no hardcoded secrets.
Rate limit: in-memory throttle on POST /api/ingestion/run (e.g. 60s per user).
"""
import logging
import re
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, session

from app.services.ingestion_pipeline import run_ingestion_pipeline
from app.services.constants import MAX_EMAILS_PER_RUN
from app.models import IngestedTransaction

logger = logging.getLogger(__name__)

ingestion_bp = Blueprint("ingestion", __name__, url_prefix="/api/ingestion")

# Rate limit: last run timestamp per user_id (in-memory; use Redis in multi-worker)
_ingestion_last_run: dict = {}
RATE_LIMIT_SECONDS = 60

# Strict after_date format: YYYY-MM-DD only
AFTER_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_after_date(value: str):
    """Validate format and parse. Returns (datetime or None, error_message)."""
    if not value or not isinstance(value, str):
        return None, None
    value = value.strip()
    if not AFTER_DATE_REGEX.match(value):
        return None, "after_date must be YYYY-MM-DD"
    try:
        return datetime.strptime(value, "%Y-%m-%d"), None
    except ValueError:
        return None, "after_date invalid date"


@ingestion_bp.route("/run", methods=["POST"])
def run_ingestion():
    """
    Manually trigger email ingestion for the current user.
    Body (optional): { "after_date": "YYYY-MM-DD", "max_emails": 50, "query": "..." }.
    Rate limited (e.g. 60s between runs per user).
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401

    now_ts = time.monotonic()
    last = _ingestion_last_run.get(user_id)
    if last is not None and (now_ts - last) < RATE_LIMIT_SECONDS:
        return jsonify({
            "message": "Rate limited",
            "retry_after_seconds": RATE_LIMIT_SECONDS,
        }), 429

    data = request.get_json(silent=True) or {}
    after_date = None
    if data.get("after_date"):
        parsed, err = _parse_after_date(data["after_date"])
        if err:
            return jsonify({"message": err}), 400
        after_date = parsed
    try:
        max_emails = min(max(int(data.get("max_emails", 50)), 1), MAX_EMAILS_PER_RUN)
    except (TypeError, ValueError):
        max_emails = 50
    query = data.get("query") or None

    _ingestion_last_run[user_id] = now_ts

    processed, new_txns, err = run_ingestion_pipeline(
        user_id=user_id,
        after_date=after_date,
        max_emails=max_emails,
        query=query,
    )
    if err:
        return jsonify({
            "message": "Ingestion failed",
            "error": err,
            "processed": processed,
            "new_transactions": new_txns,
        }), 502
    return jsonify({
        "message": "Ingestion completed",
        "emails_processed": processed,
        "new_transactions": new_txns,
    }), 200


@ingestion_bp.route("/transactions", methods=["GET"])
def list_ingested_transactions():
    """List ingested transactions for the current user (paginated)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401

    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 20))))
    q = IngestedTransaction.query.filter_by(user_id=user_id).order_by(IngestedTransaction.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for t in pagination.items:
        items.append({
            "id": t.id,
            "amount": float(t.amount),
            "transaction_type": t.transaction_type,
            "source": t.source,
            "extracted_date": t.extracted_date.isoformat() if t.extracted_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return jsonify({
        "transactions": items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
    }), 200
