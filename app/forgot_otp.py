"""
OTP generation and sending for forgot credentials (email/phone).
- OTP is stored hashed in DB; never store or log plain OTP.
- All config (SMTP/SMS) from environment via app.config.
- SMS: Twilio or any web-based HTTP API (SMS_WEB_API_URL + SMS_WEB_API_KEY).
"""
import hashlib
import hmac
import json
import random
import string
import smtplib
import urllib.request
import urllib.parse
import base64
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def generate_otp(length=6):
    """Generate a 6-digit OTP. Caller must hash before storing."""
    return "".join(random.choices(string.digits, k=length))


def hash_otp(otp):
    """Hash OTP for storage. Never store or log plain OTP."""
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def verify_otp_hash(plain_otp, stored_hash):
    """Verify user input against stored hash. Constant-time comparison."""
    if not stored_hash or not plain_otp:
        return False
    computed = hashlib.sha256(plain_otp.encode("utf-8")).hexdigest()
    return hmac.compare_digest(computed, stored_hash)


def send_email_otp(email, otp, app):
    """
    Send 6-digit OTP via SMTP. Uses env: SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD.
    OTP expires in config OTP_EXPIRY_MINUTES (default 5). Do not log OTP.
    """
    try:
        host = (app.config.get("MAIL_SERVER") or "").strip()
        port = int(app.config.get("MAIL_PORT", 587))
        user = (app.config.get("MAIL_USERNAME") or "").strip()
        raw_password = app.config.get("MAIL_PASSWORD") or ""
        # Gmail App Passwords are 16 chars; strip spaces/dashes if user copied with separators
        password = raw_password.replace(" ", "").replace("-", "").strip()
        from_addr = (app.config.get("MAIL_DEFAULT_SENDER") or user or "noreply@expenso.local").strip()
        if not host or not user or not password:
            return False
        expiry_mins = int(app.config.get("OTP_EXPIRY_MINUTES", 5))
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Expenso - Your password reset OTP"
        msg["From"] = from_addr
        msg["To"] = email
        text = f"Your OTP for password reset is: {otp}. It is valid for {expiry_mins} minutes. Do not share this code."
        msg.attach(MIMEText(text, "plain"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [email], msg.as_string())
        return True
    except Exception as e:
        if app and getattr(app, "logger", None):
            app.logger.warning("Failed to send OTP email: %s", str(e))
        return False


def send_otp_email(to_email, otp, app):
    """Alias for send_email_otp for backward compatibility."""
    return send_email_otp(to_email, otp, app)


def send_sms_otp(phone, otp, app):
    """
    Send OTP via SMS. Provider-agnostic abstraction; currently Twilio if configured.
    Uses env: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER.
    Do not log OTP.
    """
    return send_otp_sms(phone, otp, app)


def _send_sms_via_web_api(phone, body, app):
    """
    Send SMS via any HTTP API. Uses env: SMS_WEB_API_URL, SMS_WEB_API_KEY (optional).
    POST to URL with JSON: {"to": phone, "message": body}. Header: Authorization: Bearer <key> if key set.
    Adapt to your provider (MSG91, TextLocal, etc.) by setting their API URL; some need different keys in JSON.
    """
    url = (app.config.get("SMS_WEB_API_URL") or "").strip()
    key = (app.config.get("SMS_WEB_API_KEY") or "").strip()
    if not url:
        return False
    to_num = phone.strip()
    if not to_num.startswith("+"):
        to_num = "+" + to_num
    payload = json.dumps({"to": to_num, "message": body}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        if app and getattr(app, "logger", None):
            app.logger.warning("Web SMS API failed: %s", str(e))
        return False


def send_otp_sms(phone, otp, app):
    """Send OTP via Twilio if configured; else via web-based API (SMS_WEB_API_URL). Do not log OTP."""
    expiry_mins = int(app.config.get("OTP_EXPIRY_MINUTES", 5))
    body = f"Your Expenso password reset OTP is: {otp}. Valid for {expiry_mins} minutes. Do not share."
    # Try Twilio first
    sid = app.config.get("TWILIO_ACCOUNT_SID")
    token = app.config.get("TWILIO_AUTH_TOKEN")
    from_num = app.config.get("TWILIO_FROM_NUMBER")
    if sid and token and from_num:
        to_num = phone.strip()
        if not to_num.startswith("+"):
            to_num = "+" + to_num
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        data = urllib.parse.urlencode({"To": to_num, "From": from_num, "Body": body}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Basic {auth}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    return True
        except Exception as e:
            if app and getattr(app, "logger", None):
                app.logger.warning("Failed to send OTP SMS (Twilio): %s", str(e))
    # Fallback: web-based SMS API (any provider with HTTP endpoint)
    return _send_sms_via_web_api(phone, body, app)


def create_reset_token():
    return uuid.uuid4().hex


def get_otp_expiry_minutes(app=None):
    """OTP validity in minutes (default 5). Pass app to use config."""
    if app:
        return int(app.config.get("OTP_EXPIRY_MINUTES", 5))
    return 5
