"""
Synthetic transaction data generator for Expenso.
Generates 3–6 months of realistic financial transactions per user and inserts into IngestedTransaction.
Run from project root: python scripts/generate_synthetic_data.py [--clear] [--user-ids 1 2 3]
"""
import argparse
import os
import random
import sys

# Project root on path so "app" and "config" resolve
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app import create_app
from app.models.ingestion_models import db, IngestedTransaction
from app.utils.synthetic_data import (
    SYNTHETIC_MARKER,
    DAYS_BACK,
    MIN_TXNS_PER_USER,
    MAX_TXNS_PER_USER,
    generate_transactions_for_user,
)


def get_user_ids(app) -> list:
    """Fetch existing user IDs from users table (MySQL pool)."""
    if not getattr(app, "mysql_pool", None):
        return []
    conn = app.mysql_pool.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users")
        ids = [r["id"] for r in cursor.fetchall()]
        cursor.close()
        return ids
    finally:
        conn.close()


def clear_synthetic_data() -> int:
    """Delete rows created by this script (raw_text starts with SYNTHETIC:). Call within app_context. Returns deleted count."""
    deleted = (
        db.session.query(IngestedTransaction)
        .filter(IngestedTransaction.raw_text.like(f"{SYNTHETIC_MARKER}%"))
        .delete(synchronize_session=False)
    )
    db.session.commit()
    return deleted


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic IngestedTransaction data")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear previous synthetic data (raw_text LIKE 'SYNTHETIC:%') before generating",
    )
    parser.add_argument(
        "--user-ids",
        type=int,
        nargs="+",
        default=None,
        help="User IDs to generate for; default: all users from users table",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DAYS_BACK,
        help=f"Spread transactions over this many days (default {DAYS_BACK})",
    )
    parser.add_argument(
        "--min-txns",
        type=int,
        default=MIN_TXNS_PER_USER,
        help=f"Min transactions per user (default {MIN_TXNS_PER_USER})",
    )
    parser.add_argument(
        "--max-txns",
        type=int,
        default=MAX_TXNS_PER_USER,
        help=f"Max transactions per user (default {MAX_TXNS_PER_USER})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Bulk insert batch size (default 500)",
    )
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        if args.user_ids is not None:
            user_ids = args.user_ids
            print(f"[generate_synthetic_data] Using user IDs: {user_ids}")
        else:
            user_ids = get_user_ids(app)
            if not user_ids:
                print("[generate_synthetic_data] No users found. Use --user-ids 1 2 3 or create users first.")
                sys.exit(1)
            print(f"[generate_synthetic_data] Found {len(user_ids)} user(s): {user_ids}")

        if args.clear:
            deleted = clear_synthetic_data()
            print(f"[generate_synthetic_data] Cleared previous synthetic data: {deleted} row(s) deleted.")

        total_inserted = 0
        for uid in user_ids:
            n = random.randint(
                max(args.min_txns, 0),
                max(args.max_txns, args.min_txns),
            )
            rows = generate_transactions_for_user(uid, n, args.days)
            batch_size = max(1, args.batch_size)
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                db.session.bulk_insert_mappings(IngestedTransaction, batch)
            db.session.commit()
            total_inserted += len(rows)
            print(f"[generate_synthetic_data] user_id={uid} inserted={len(rows)} (total so far={total_inserted})")

        print(f"[generate_synthetic_data] Done. Total transactions inserted: {total_inserted}")


if __name__ == "__main__":
    main()
