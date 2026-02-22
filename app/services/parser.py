"""
Transaction relevance and extraction. Used by both email and (later) SMS ingestion.
Keyword threshold + regex-based amount/type/date extraction.
"""
import re
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

KEYWORDS = [
    "invoice", "transaction", "credited", "debited", "upi", "payment", "order", "bank",
    "amount", "rs.", "inr", "rupee", "balance", "withdrawal", "deposit", "transfer",
    "paid", "received", "refund", "bill", "subscription", "debit", "credit",
]
KEYWORD_MIN_MATCHES = 2

AMOUNT_PATTERN = re.compile(
    r"₹?\s*Rs\.?\s*(\d+(?:,\d+)*(?:\.\d{2})?)",
    re.IGNORECASE
)
AMOUNT_FALLBACK = re.compile(r"\b(\d+(?:,\d+)*\.\d{2})\b")
CREDITED_PATTERN = re.compile(r"\b(credited|received|deposit|credit)\b", re.IGNORECASE)
DEBITED_PATTERN = re.compile(r"\b(debited|paid|withdrawal|debit|sent)\b", re.IGNORECASE)
DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"),
    re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b"),
    re.compile(r"(?:on|date|dt)[:\s]+(\d{1,2})[/-](\d{1,2})[/-](\d{4})", re.IGNORECASE),
]


def is_relevant(text: str) -> bool:
    """True if text has at least KEYWORD_MIN_MATCHES transaction keywords."""
    if not text or not text.strip():
        return False
    lower = text.lower()
    return sum(1 for kw in KEYWORDS if kw in lower) >= KEYWORD_MIN_MATCHES


def _normalize_amount(amount_str: str) -> Optional[float]:
    if not amount_str:
        return None
    try:
        return float(amount_str.replace(",", "").strip())
    except ValueError:
        return None


def _parse_amount(text: str) -> Optional[float]:
    for pattern in (AMOUNT_PATTERN, AMOUNT_FALLBACK):
        m = pattern.search(text)
        if m:
            val = _normalize_amount(m.group(1))
            if val is not None and val > 0:
                return val
    return None


def _parse_transaction_type(text: str) -> Optional[str]:
    if CREDITED_PATTERN.search(text):
        return "credited"
    if DEBITED_PATTERN.search(text):
        return "debited"
    return None


def _parse_date(text: str) -> Optional[datetime]:
    for pattern in DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                g = m.groups()
                if len(g) == 3:
                    if len(g[0]) == 4:
                        y, mo, d = int(g[0]), int(g[1]), int(g[2])
                    else:
                        d, mo, y = int(g[0]), int(g[1]), int(g[2])
                    if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2100:
                        return datetime(y, mo, d).date()
            except (ValueError, TypeError):
                continue
    return None


def extract_transaction_data(text: str) -> Optional[dict]:
    """Extract amount, transaction_type, extracted_date. None if no amount."""
    if not text or not is_relevant(text):
        return None
    amount = _parse_amount(text)
    if amount is None:
        return None
    return {
        "amount": amount,
        "transaction_type": _parse_transaction_type(text),
        "extracted_date": _parse_date(text),
    }
