"""
Shared synthetic transaction generation. Used by scripts/generate_synthetic_data.py and ensure_user_has_synthetic_data.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

SYNTHETIC_MARKER = "SYNTHETIC:"
DAYS_BACK = 180
MIN_TXNS_PER_USER = 300
MAX_TXNS_PER_USER = 600

CATEGORY_RULES = {
    "Food": ("debited", 100, 800),
    "Travel": ("debited", 150, 2000),
    "Shopping": ("debited", 500, 15000),
    "Entertainment": ("debited", 99, 1500),
    "Bills": ("debited", 500, 5000),
    "Salary": ("credited", 20000, 80000),
    "Transfer": ("debited", 50, 50000),
}

MERCHANTS = [
    ("Swiggy", "Food"),
    ("Zomato", "Food"),
    ("Amazon", "Shopping"),
    ("Flipkart", "Shopping"),
    ("Uber", "Travel"),
    ("Ola", "Travel"),
    ("Netflix", "Entertainment"),
    ("Spotify", "Entertainment"),
    ("SBI", "Bills"),
    ("HDFC", "Bills"),
    ("ICICI", "Bills"),
    ("UPI transfers", "Transfer"),
]

CATEGORY_WEIGHTS = {
    "Food": 22,
    "Travel": 15,
    "Shopping": 18,
    "Entertainment": 12,
    "Bills": 10,
    "Salary": 3,
    "Transfer": 20,
}


def _random_date_in_range(days_back: int) -> datetime:
    now = datetime.utcnow()
    start = now - timedelta(days=days_back)
    delta = now - start
    sec = random.randint(0, max(0, int(delta.total_seconds())))
    return start + timedelta(seconds=sec)


def _amount_for_category(category: str) -> tuple:
    rule = CATEGORY_RULES[category]
    tx_type = rule[0]
    lo, hi = rule[1], rule[2]
    amount = round(random.uniform(lo, hi), 2)
    return amount, tx_type


def _pick_category() -> str:
    choices = list(CATEGORY_WEIGHTS.keys())
    weights = [CATEGORY_WEIGHTS[c] for c in choices]
    return random.choices(choices, weights=weights, k=1)[0]


def _merchant_for_category(category: str) -> str:
    if category == "Salary":
        return random.choice(["SBI", "HDFC", "ICICI", "Employer"])
    options = [m for m, c in MERCHANTS if c == category]
    return random.choice(options) if options else "UPI"


def _raw_text_sms(merchant: str, amount: float, tx_type: str, dt: datetime) -> str:
    date_str = dt.strftime("%d-%m-%Y")
    if tx_type == "credited":
        return (
            f"{SYNTHETIC_MARKER} Rs.{amount:.2f} credited to a/c XX1234 on {date_str}. "
            f"Ref {merchant}. Avl bal Rs.XXXXX."
        )
    return (
        f"{SYNTHETIC_MARKER} Rs.{amount:.2f} debited from a/c XX1234 on {date_str}. "
        f"Info {merchant}. UPI/ATM."
    )


def generate_transactions_for_user(
    user_id: int,
    count: int,
    days_back: int = DAYS_BACK,
) -> List[dict]:
    """Generate count transactions for user_id; returns list of dicts for bulk_insert_mappings (no id)."""
    rows = []
    for _ in range(count):
        category = _pick_category()
        amount, tx_type = _amount_for_category(category)
        merchant = _merchant_for_category(category)
        created_at = _random_date_in_range(days_back)
        extracted_date = created_at.date()
        raw_text = _raw_text_sms(merchant, amount, tx_type, created_at)
        source = random.choice(["email", "sms"])
        rows.append({
            "user_id": user_id,
            "amount": Decimal(str(round(amount, 2))),
            "transaction_type": tx_type,
            "source": source,
            "raw_text": raw_text,
            "extracted_date": extracted_date,
            "created_at": created_at,
        })
    return rows
