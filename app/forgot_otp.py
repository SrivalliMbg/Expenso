"""OTP generation and sending for forgot credentials (email/phone)."""
import random
import string
import smtplib
import urllib.request
import urllib.error
import urllib.parse
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import uuid


def generate_otp(length=6):
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email, otp, app):
    """Send OTP via SMTP if configured; otherwise return False."""
    try:
        host = app.config.get("MAIL_SERVER")
        port = app.config.get("MAIL_PORT", 587)
        user = app.config.get("MAIL_USERNAME")
        password = app.config.get("MAIL_PASSWORD")
        from_addr = app.config.get("MAIL_DEFAULT_SENDER", user or "noreply@expenso.local")
        if not host or not user or not password:
            return False
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Expenso - Your password reset OTP"
        msg["From"] = from_addr
        msg["To"] = to_email
        text = f"Your OTP for password reset is: {otp}. It is valid for 10 minutes. Do not share this code."
        msg.attach(MIMEText(text, "plain"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        return True
    except Exception as e:
        if app.logger:
            app.logger.warning("Failed to send OTP email: %s", e)
        return False


def send_otp_sms(phone, otp, app):
    """Send OTP via Twilio SMS if configured; otherwise return False."""
    sid = app.config.get("TWILIO_ACCOUNT_SID")
    token = app.config.get("TWILIO_AUTH_TOKEN")
    from_num = app.config.get("TWILIO_FROM_NUMBER")
    if not sid or not token or not from_num:
        return False
    # Normalize phone: ensure it has a + for Twilio
    to_num = phone.strip()
    if not to_num.startswith("+"):
        to_num = "+" + to_num
    body = f"Your Expenso password reset OTP is: {otp}. Valid for 10 minutes. Do not share."
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    data = urllib.parse.urlencode({
        "To": to_num,
        "From": from_num,
        "Body": body,
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        if app.logger:
            app.logger.warning("Failed to send OTP SMS: %s", e)
        return False


def create_reset_token():
    return uuid.uuid4().hex


def get_otp_expiry_minutes():
    return 10
