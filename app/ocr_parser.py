"""
OCR and text parsing for messages/emails and PDFs: extract financial data for categorisation and analysis.
Parses SMS, email body, image (screenshot), or PDF (policies, insurance, investments) into structured data.
"""

import re
from datetime import datetime
from io import BytesIO

# Optional: OCR from image (requires pytesseract + Tesseract installed)
try:
    import pytesseract
    from PIL import Image
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

# Optional: PDF text extraction
try:
    from pypdf import PdfReader
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

# Categories used in app (match chatbot and dashboard)
CATEGORIES = [
    "Food", "Transport", "Entertainment", "Shopping", "Healthcare", "Education",
    "Bills", "Transfer", "Investment", "Insurance", "Other"
]

# Keywords -> category for auto-categorisation
CATEGORY_KEYWORDS = {
    "Food": ["food", "restaurant", "swiggy", "zomato", "grocery", "supermarket", "cafe", "dominos", "mcdonald", "dining", "kitchen", "bakery"],
    "Transport": ["fuel", "petrol", "diesel", "uber", "ola", "rapido", "metro", "bus", "train", "parking", "toll", "cab"],
    "Entertainment": ["netflix", "prime", "hotstar", "spotify", "movie", "cinema", "game", "entertainment", "subscription"],
    "Shopping": ["amazon", "flipkart", "mall", "shopping", "store", "purchase", "order"],
    "Healthcare": ["hospital", "pharmacy", "medical", "doctor", "apollo", "1mg", "health"],
    "Education": ["school", "college", "course", "udemy", "books", "education", "fee", "tuition"],
    "Bills": ["electricity", "water", "gas", "broadband", "wifi", "recharge", "bill", "jio", "airtel", "vodafone", "dth"],
    "Transfer": ["transfer", "imps", "neft", "upi", "sent to", "received from", "self transfer", "to self"],
    "Investment": ["sip", "mutual fund", "investment", "demand draft", "dd"],
    "Insurance": ["insurance", "premium", "policy"],
    "Other": [],
}


def extract_text_from_image(image_bytes):
    """Extract text from an image (screenshot/photo) using OCR. Returns plain text or empty string if OCR not available."""
    if not _OCR_AVAILABLE:
        return ""
    try:
        img = Image.open(BytesIO(image_bytes))
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        return pytesseract.image_to_string(img) or ""
    except Exception:
        return ""


def extract_text_from_pdf(pdf_bytes):
    """Extract text from a PDF (policy, statement, etc.). Returns plain text or empty string if pypdf not available."""
    if not _PDF_AVAILABLE:
        return ""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


def _normalize_amount(s):
    """Parse amount string to float. Handles Rs 1,234.56 / 1234.56 / 1,234."""
    if not s:
        return None
    s = str(s).replace(",", "").replace(" ", "").strip()
    m = re.search(r"[\d.]+", s)
    if m:
        try:
            return round(float(m.group()), 2)
        except ValueError:
            pass
    return None


def _parse_date(s):
    """Try to parse a date from string. Returns date object or None."""
    if not s or len(s) < 4:
        return None
    s = s.strip()
    # DD-MM-YYYY, DD/MM/YYYY, DD-MM-YY, DD Mon YYYY
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%d %b %Y", "%d %b %y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s[:20], fmt).date()
        except (ValueError, TypeError):
            continue
    # Fallback: look for 2-4 digit year and digits before
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000 if y < 50 else 1900
        try:
            from datetime import date
            return date(y, mo, d)
        except ValueError:
            pass
    return None


def _categorise(description):
    """Map description to one of CATEGORIES using keywords."""
    if not description:
        return "Other"
    d = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == "Other":
            continue
        if any(k in d for k in keywords):
            return category
    return "Other"


def parse_financial_text(text):
    """
    Parse raw text (SMS, email body, OCR output) into a list of financial entries.
    Each entry: { "title": str, "amount": float, "type": "Credit"|"Debit", "date": date|None, "category": str }
    """
    if not text or not text.strip():
        return []
    text = text.strip()
    entries = []
    # Common patterns: "debited with Rs 500" / "credited with INR 1000" / "Rs. 234.56 spent at X"
    # Split into lines and look for amount + debit/credit + optional date
    amount_pattern = re.compile(
        r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{2})?)|"
        r"(?:debited|deducted|spent|paid|withdrawn)[^\d]*([\d,]+(?:\.\d{2})?)|"
        r"(?:credited|received|deposited)[^\d]*([\d,]+(?:\.\d{2})?)|"
        r"([\d,]+(?:\.\d{2})?)\s*(?:rs|inr|₹)",
        re.IGNORECASE
    )
    date_pattern = re.compile(
        r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b|"
        r"\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})\b",
        re.IGNORECASE
    )
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    seen = set()
    for line in lines:
        amt_match = amount_pattern.search(line)
        if not amt_match:
            continue
        amount = None
        for g in amt_match.groups():
            if g:
                amount = _normalize_amount(g)
                break
        if amount is None or amount <= 0:
            continue
        # Debit vs credit
        line_lower = line.lower()
        if "credited" in line_lower or "received" in line_lower or "deposited" in line_lower or "credit" in line_lower:
            txn_type = "Credit"
        elif "debited" in line_lower or "deducted" in line_lower or "spent" in line_lower or "paid" in line_lower or "withdrawn" in line_lower or "debit" in line_lower:
            txn_type = "Debit"
        else:
            txn_type = "Debit"
        date_val = None
        dm = date_pattern.search(line)
        if dm:
            for g in dm.groups():
                if g:
                    date_val = _parse_date(g)
                    break
        if not date_val:
            date_val = datetime.now().date()
        # Title: first 80 chars of line, or "Imported"
        title = line[:80] if len(line) <= 120 else (line[:77] + "...")
        category = _categorise(title)
        key = (title[:50], amount, txn_type, str(date_val))
        if key in seen:
            continue
        seen.add(key)
        entries.append({
            "title": title,
            "amount": amount,
            "type": txn_type,
            "date": date_val.isoformat() if date_val else None,
            "category": category,
        })
    # If no line-based match, try whole-text single amount
    if not entries and text:
        amt_match = amount_pattern.search(text)
        if amt_match:
            amount = None
            for g in amt_match.groups():
                if g:
                    amount = _normalize_amount(g)
                    break
            if amount is not None and amount > 0:
                line_lower = text.lower()
                txn_type = "Credit" if "credit" in line_lower and "debit" not in line_lower else "Debit"
                date_val = None
                dm = date_pattern.search(text)
                if dm:
                    for g in dm.groups():
                        if g:
                            date_val = _parse_date(g)
                            break
                if not date_val:
                    date_val = datetime.now().date()
                entries.append({
                    "title": text[:80] if len(text) <= 80 else (text[:77] + "..."),
                    "amount": amount,
                    "type": txn_type,
                    "date": date_val.isoformat(),
                    "category": _categorise(text),
                })
    return entries


def _first_amount_in_text(text, after_keyword=None):
    """Find first amount (Rs/INR/number) in text, optionally after a keyword. Returns (amount, None) or (None, None)."""
    if after_keyword:
        idx = text.lower().find(after_keyword.lower())
        if idx >= 0:
            text = text[idx + len(after_keyword):][:500]
    amount_pattern = re.compile(
        r"(?:rs\.?|inr|₹|premium|coverage|sum\s+assured|amount)[\s:]*([\d,]+(?:\.\d{2})?)|([\d,]+(?:\.\d{2})?)\s*(?:rs|inr|₹)",
        re.IGNORECASE
    )
    m = amount_pattern.search(text)
    if not m:
        return None, None
    for g in m.groups():
        if g:
            return _normalize_amount(g), m.group(0)
    return None, None


def parse_policy_insurance_text(text):
    """
    Parse text (e.g. from policy PDF) for insurance/policy data.
    Returns list of dicts: { policy_name, policy_type, premium_amount, coverage_amount, next_due_date }.
    """
    if not text or not text.strip():
        return []
    text = text.strip()
    lower = text.lower()
    if not any(k in lower for k in ("policy", "insurance", "premium", "coverage", "sum assured", "life insurance", "health insurance")):
        return []
    policies = []
    premium, _ = _first_amount_in_text(text, "premium")
    if premium is None:
        premium, _ = _first_amount_in_text(text, "annual premium")
    if premium is None:
        premium, _ = _first_amount_in_text(text)
    coverage, _ = _first_amount_in_text(text, "coverage")
    if coverage is None:
        coverage, _ = _first_amount_in_text(text, "sum assured")
    if coverage is None:
        coverage, _ = _first_amount_in_text(text, "assured")
    policy_type = "Other"
    if "life" in lower and "insurance" in lower:
        policy_type = "Life"
    elif "health" in lower:
        policy_type = "Health"
    elif "motor" in lower or "vehicle" in lower:
        policy_type = "Motor"
    elif "term" in lower:
        policy_type = "Term"
    next_due = None
    for m in re.finditer(r"(?:next\s+due|due\s+date|renewal|payment\s+date)[\s:]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", lower, re.IGNORECASE):
        next_due = _parse_date(m.group(1))
        if next_due:
            break
    if not next_due:
        for m in re.finditer(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b", text):
            next_due = _parse_date(m.group(1))
            if next_due:
                break
    policy_name = "Imported policy"
    for m in re.finditer(r"(?:policy\s+(?:no\.?|number|#)|policy\s+name|product)[\s:]*([A-Za-z0-9\s\-/]+?)(?:\n|$|premium|coverage)", text, re.IGNORECASE):
        name = m.group(1).strip()[:120]
        if len(name) > 3:
            policy_name = name
            break
    if premium is not None or coverage is not None:
        policies.append({
            "policy_name": policy_name[:255],
            "policy_type": policy_type,
            "premium_amount": float(premium or 0),
            "coverage_amount": float(coverage or 0),
            "next_due_date": next_due.isoformat() if next_due else None,
        })
    return policies


def parse_investment_text(text):
    """
    Parse text (e.g. from statement PDF) for investment data.
    Returns list of dicts: { investment_type, amount, start_date, maturity_date }.
    """
    if not text or not text.strip():
        return []
    text = text.strip()
    lower = text.lower()
    if not any(k in lower for k in ("investment", "sip", "mutual fund", "maturity", "principal", "invested", "folio", "nav")):
        return []
    investments = []
    amount, _ = _first_amount_in_text(text, "invested")
    if amount is None:
        amount, _ = _first_amount_in_text(text, "principal")
    if amount is None:
        amount, _ = _first_amount_in_text(text, "amount")
    if amount is None:
        amount, _ = _first_amount_in_text(text)
    inv_type = "Other"
    if "sip" in lower or "systematic" in lower:
        inv_type = "SIP"
    elif "mutual fund" in lower or "mf" in lower:
        inv_type = "Mutual Fund"
    elif "fd" in lower or "fixed deposit" in lower:
        inv_type = "Fixed Deposit"
    elif "ppf" in lower:
        inv_type = "PPF"
    elif "elss" in lower:
        inv_type = "ELSS"
    elif "nps" in lower:
        inv_type = "NPS"
    start_date = None
    maturity_date = None
    for m in re.finditer(r"(?:start|investment|purchase)\s*date[\s:]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", lower, re.IGNORECASE):
        start_date = _parse_date(m.group(1))
        if start_date:
            break
    if not start_date:
        for m in re.finditer(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b", text):
            start_date = _parse_date(m.group(1))
            if start_date:
                break
    for m in re.finditer(r"(?:maturity|end|redemption)\s*date[\s:]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", lower, re.IGNORECASE):
        maturity_date = _parse_date(m.group(1))
        if maturity_date:
            break
    if not maturity_date and "maturity" in lower:
        for m in re.finditer(r"maturity[\s:]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", lower, re.IGNORECASE):
            maturity_date = _parse_date(m.group(1))
            if maturity_date:
                break
    if amount is not None and amount > 0:
        investments.append({
            "investment_type": inv_type,
            "amount": float(amount),
            "start_date": start_date.isoformat() if start_date else None,
            "maturity_date": maturity_date.isoformat() if maturity_date else None,
        })
    return investments
