"""
SMS upload and ingestion routes. Upload stores raw SMS; ingest runs pipeline (parser + IngestedTransaction).

Optional Android integration: App should (1) request READ_SMS permission, (2) filter messages locally
(e.g. by sender or date) to reduce payload and privacy surface, (3) send only recent SMS to POST /api/sms/upload.
"""
import logging
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, session

from app.services.ingestion_pipeline import run_sms_ingestion_pipeline
from app.services.constants import SMS_BODY_MAX_LENGTH, MAX_SMS_PER_RUN
from app.models import db, UploadedSMS

logger = logging.getLogger(__name__)

sms_bp = Blueprint("sms", __name__, url_prefix="/api/sms")

AFTER_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_after_date(value: str):
    """Validate YYYY-MM-DD and parse. Returns (datetime or None, error_message)."""
    if not value or not isinstance(value, str):
        return None, None
    value = value.strip()
    if not AFTER_DATE_REGEX.match(value):
        return None, "after_date must be YYYY-MM-DD"
    try:
        return datetime.strptime(value, "%Y-%m-%d"), None
    except ValueError:
        return None, "after_date invalid date"


def _truncate_body(body: str, max_len: int = SMS_BODY_MAX_LENGTH) -> str:
    if body is None:
        return ""
    s = str(body)
    return s[:max_len] if len(s) > max_len else s


@sms_bp.route("/upload", methods=["POST"])
def upload_sms():
    """
    Store SMS messages from client (e.g. Android). No parsing; just persist.
    Body: { "messages": [ { "id": "device_sms_id", "body": "text", "timestamp": "2025-02-22T10:30:00" } ] }.
    Duplicates (same user_id + device_sms_id) are skipped. Returns count inserted.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401

    data = request.get_json(silent=True)
    if not data or "messages" not in data:
        return jsonify({"message": "Missing 'messages' array"}), 400

    raw_list = data.get("messages")
    if not isinstance(raw_list, list):
        return jsonify({"message": "'messages' must be an array"}), 400

    inserted = 0
    seen_ids = set()

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        device_sms_id = item.get("id")
        if not device_sms_id or not str(device_sms_id).strip():
            continue
        device_sms_id = str(device_sms_id).strip()
        if device_sms_id in seen_ids:
            continue
        seen_ids.add(device_sms_id)

        body = item.get("body")
        body_safe = _truncate_body(body if body is not None else "")

        ts = None
        if item.get("timestamp"):
            try:
                ts_str = str(item["timestamp"]).strip()
                if "T" in ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.strptime(ts_str[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                pass

        existing = UploadedSMS.query.filter_by(
            user_id=user_id, device_sms_id=device_sms_id
        ).first()
        if existing:
            continue

        try:
            rec = UploadedSMS(
                user_id=user_id,
                device_sms_id=device_sms_id,
                body=body_safe or None,
                timestamp=ts,
            )
            db.session.add(rec)
            inserted += 1
        except Exception as e:
            logger.warning("upload_sms insert failed for device_sms_id=%s: %s", device_sms_id, e)
            db.session.rollback()
            return jsonify({"message": "Upload failed", "error": str(e)}), 502

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("upload_sms commit failed: %s", e)
        return jsonify({"message": "Upload failed", "error": str(e)}), 502

    logger.info(
        "sms.upload user_id=%s inserted=%s",
        user_id, inserted,
        extra={"event": "sms_upload", "user_id": user_id, "inserted": inserted},
    )
    return jsonify({"message": "Upload completed", "inserted": inserted}), 200


@sms_bp.route("/ingest", methods=["POST"])
def run_sms_ingest():
    """
    Run SMS ingestion pipeline for the current user.
    Body (optional): { "after_date": "YYYY-MM-DD", "max_messages": 100 }. max_messages capped at 200.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    after_date = None
    if data.get("after_date"):
        parsed, err = _parse_after_date(data["after_date"])
        if err:
            return jsonify({"message": err}), 400
        after_date = parsed

    try:
        max_messages = min(max(int(data.get("max_messages", 100)), 1), MAX_SMS_PER_RUN)
    except (TypeError, ValueError):
        max_messages = 100

    processed, new_txns, err = run_sms_ingestion_pipeline(
        user_id=user_id,
        after_date=after_date,
        max_messages=max_messages,
    )
    if err:
        return jsonify({
            "message": "SMS ingestion failed",
            "error": err,
            "processed": processed,
            "new_transactions": new_txns,
        }), 502
    return jsonify({
        "message": "SMS ingestion completed",
        "processed_count": processed,
        "new_transactions": new_txns,
    }), 200
