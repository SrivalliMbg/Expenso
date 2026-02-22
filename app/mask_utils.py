"""
Mask sensitive data in API responses. Never return full account numbers, email, or phone.
"""
import re


def mask_account_number(acc_no):
    """Show last 4 digits only; rest as *."""
    if acc_no is None or acc_no == "":
        return ""
    s = str(acc_no).strip()
    if len(s) <= 4:
        return "*" * len(s)
    return "*" * (len(s) - 4) + s[-4:]


def mask_email(email):
    """First char + **** (e.g. a****@example.com)."""
    if not email or not isinstance(email, str):
        return ""
    e = email.strip()
    if not e or "@" not in e:
        return "****"
    local, _, domain = e.partition("@")
    if not local:
        return "****@" + domain
    return local[0] + "****@" + domain


def mask_phone(phone):
    """Show last 3 digits only (e.g. *******890)."""
    if phone is None or phone == "":
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) <= 3:
        return "*" * len(digits)
    return "*" * (len(digits) - 3) + digits[-3:]


def mask_sensitive_data(data):
    """
    Return a masked copy of data. Masks: account numbers (last 4), email (first char + ****), phone (last 3).
    Accepts dict or list of dicts; recurses into nested dicts and lists.
    """
    if data is None:
        return None
    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    if not isinstance(data, dict):
        return data
    out = {}
    for k, v in data.items():
        key_lower = k.lower()
        if v is None:
            out[k] = None
        elif key_lower in ("acc_no", "account_number", "card_number"):
            out[k] = mask_account_number(v)
        elif key_lower == "email":
            out[k] = mask_email(v)
        elif key_lower == "phone":
            out[k] = mask_phone(v)
        elif isinstance(v, dict):
            out[k] = mask_sensitive_data(v)
        elif isinstance(v, list):
            out[k] = mask_sensitive_data(v)
        else:
            out[k] = v
    return out
