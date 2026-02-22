"""
Ensure a user has synthetic transaction data. Used when logged-in user has no transactions
(e.g. data was generated for a different user_id). DEMO_MODE=True copies from any user who
already has transactions; DEMO_MODE=False generates a new dataset. No hardcoded user_id.
"""
import logging
import random
from typing import Tuple

from flask import current_app

from .synthetic_data import (
    SYNTHETIC_MARKER,
    DAYS_BACK,
    MIN_TXNS_PER_USER,
    MAX_TXNS_PER_USER,
    generate_transactions_for_user,
)

logger = logging.getLogger(__name__)
BATCH_SIZE = 500


def _is_demo_mode() -> bool:
    """DEMO_MODE default False. Read from app config if available, else os.environ."""
    if current_app:
        return current_app.config.get("DEMO_MODE", False)
    import os
    return os.environ.get("DEMO_MODE", "").strip().lower() in ("true", "1", "yes")


def _find_template_user_id(exclude_user_id: int):
    """
    Return a user_id that has at least one IngestedTransaction (any such user).
    No hardcoded template user_id. Returns None if no suitable user exists.
    """
    from app.models import IngestedTransaction
    row = (
        IngestedTransaction.query.with_entities(IngestedTransaction.user_id)
        .filter(IngestedTransaction.user_id != exclude_user_id)
        .group_by(IngestedTransaction.user_id)
        .limit(1)
        .first()
    )
    return row[0] if row else None


def ensure_user_has_synthetic_data(user_id: int) -> Tuple[str, int]:
    """
    If user has no IngestedTransaction rows, either copy from any existing user (DEMO_MODE=True)
    or generate a new synthetic dataset (DEMO_MODE=False). Strict multi-user isolation; all
    writes in a single transaction with rollback on failure.

    Returns (action_taken, count): "already_has_data" | "copied" | "generated", and rows added (0 if already_has_data).
    """
    from app.models import db, IngestedTransaction

    count = IngestedTransaction.query.filter_by(user_id=user_id).count()
    if count > 0:
        logger.info("User already has transactions. user_id=%s count=%s", user_id, count)
        return "already_has_data", 0

    try:
        if _is_demo_mode():
            template_uid = _find_template_user_id(user_id)
            if template_uid is not None:
                rows = (
                    IngestedTransaction.query.filter_by(user_id=template_uid)
                    .filter(IngestedTransaction.raw_text.like(f"{SYNTHETIC_MARKER}%"))
                    .all()
                )
                if rows:
                    mappings = [
                        {
                            "user_id": user_id,
                            "amount": r.amount,
                            "transaction_type": r.transaction_type,
                            "source": r.source,
                            "raw_text": r.raw_text,
                            "extracted_date": r.extracted_date,
                            "created_at": r.created_at,
                        }
                        for r in rows
                    ]
                    for i in range(0, len(mappings), BATCH_SIZE):
                        db.session.bulk_insert_mappings(IngestedTransaction, mappings[i : i + BATCH_SIZE])
                    db.session.commit()
                    logger.info("Synthetic data copied to user %s (from user %s, count=%s)", user_id, template_uid, len(mappings))
                    return "copied", len(mappings)

        n = random.randint(MIN_TXNS_PER_USER, MAX_TXNS_PER_USER)
        new_rows = generate_transactions_for_user(user_id, n, DAYS_BACK)
        for i in range(0, len(new_rows), BATCH_SIZE):
            db.session.bulk_insert_mappings(IngestedTransaction, new_rows[i : i + BATCH_SIZE])
        db.session.commit()
        logger.info("Synthetic data generated for user %s. count=%s", user_id, len(new_rows))
        return "generated", len(new_rows)
    except Exception as e:
        db.session.rollback()
        logger.exception("ensure_user_has_synthetic_data failed for user_id=%s: %s", user_id, e)
        raise
