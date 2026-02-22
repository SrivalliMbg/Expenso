"""
Expenso configuration. All secrets must come from environment variables in production.
Set env vars or use .env (e.g. python-dotenv) — no hardcoded secrets.
Supports DATABASE_URL (e.g. from Render) or MYSQL_HOST/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DB.
"""
import os
from urllib.parse import quote_plus, urlparse


def _env(key, default=""):
    """Read from environment; empty string if unset."""
    return os.environ.get(key, default).strip()


def _parse_database_url():
    """If DATABASE_URL is set, return (host, user, password, db, uri). Else return None."""
    url = _env("DATABASE_URL")
    if not url:
        return None
    # Support mysql:// and mysql+mysqlconnector://
    if "mysql" not in url.split(":")[0].lower():
        return None
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 3306
        user = parsed.username or "root"
        password = parsed.password or ""
        db = (parsed.path or "/").lstrip("/") or "expenso_db"
        uri = f"mysql+mysqlconnector://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{db}"
        return (host, user, password, db, uri)
    except Exception:
        return None


_db_from_url = _parse_database_url()

class Config:
    # Production: FLASK_ENV=production, DEBUG=False (set in Dockerfile / Render env)
    FLASK_ENV = _env("FLASK_ENV") or "production"
    DEBUG = _env("DEBUG", "").lower() in ("true", "1", "yes")

    # Database: prefer DATABASE_URL (Render), else MYSQL_* env vars
    if _db_from_url:
        _host, _user, _pw, _dbname = _db_from_url[0], _db_from_url[1], _db_from_url[2], _db_from_url[3]
        MYSQL_HOST = _host
        MYSQL_USER = _user
        MYSQL_PASSWORD = _pw or ""
        MYSQL_DB = _dbname
    else:
        MYSQL_HOST = _env("MYSQL_HOST") or "localhost"
        MYSQL_USER = _env("MYSQL_USER") or "root"
        MYSQL_PASSWORD = _env("MYSQL_PASSWORD") or ""
        MYSQL_DB = _env("MYSQL_DB") or "expenso_db"

    # Flask secret (must set SECRET_KEY in production)
    SECRET_KEY = _env("SECRET_KEY") or os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

    # Email / SMTP (env preferred: SMTP_* or MAIL_*)
    MAIL_SERVER = _env("SMTP_SERVER") or _env("MAIL_SERVER")
    MAIL_PORT = int(_env("SMTP_PORT") or _env("MAIL_PORT") or "587")
    MAIL_USERNAME = _env("SMTP_USERNAME") or _env("MAIL_USERNAME")
    MAIL_PASSWORD = _env("SMTP_PASSWORD") or _env("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = _env("MAIL_DEFAULT_SENDER") or _env("SMTP_USERNAME") or _env("MAIL_USERNAME")

    # SMS: Twilio (optional) or web-based API (any provider with HTTP API)
    TWILIO_ACCOUNT_SID = _env("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = _env("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER = _env("TWILIO_FROM_NUMBER")
    # Web-based SMS (e.g. MSG91, TextLocal, or any REST gateway). If set, used when Twilio not configured.
    SMS_WEB_API_URL = _env("SMS_WEB_API_URL")
    SMS_WEB_API_KEY = _env("SMS_WEB_API_KEY")

    # OTP / Forgot password
    FORGOT_OTP_DEV_SHOW = _env("FORGOT_OTP_DEV_SHOW", "").lower() in ("1", "true", "yes")
    OTP_EXPIRY_MINUTES = int(_env("OTP_EXPIRY_MINUTES") or "5")
    OTP_RATE_LIMIT_COUNT = int(_env("OTP_RATE_LIMIT_COUNT") or "5")
    OTP_RATE_LIMIT_WINDOW_MINUTES = int(_env("OTP_RATE_LIMIT_WINDOW_MINUTES") or "10")

    # Gmail OAuth (placeholder; no message reading yet)
    GOOGLE_CLIENT_ID = _env("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = _env("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = _env("GOOGLE_REDIRECT_URI")
    OAUTH_ENCRYPTION_KEY = _env("OAUTH_ENCRYPTION_KEY")

    # Seed user: when a user has no transactions, optionally copy from another (DEMO_MODE) or generate new.
    # Default False: generate new synthetic data. True: copy from any user who already has transactions.
    DEMO_MODE = _env("DEMO_MODE", "").lower() in ("true", "1", "yes")

    # SQLAlchemy (same DB as app; for ingestion models)
    if _db_from_url:
        SQLALCHEMY_DATABASE_URI = _db_from_url[4]
    else:
        _pw = _env("MYSQL_PASSWORD") or ""
        _user = _env("MYSQL_USER") or "root"
        _host = _env("MYSQL_HOST") or "localhost"
        _db = _env("MYSQL_DB") or "expenso_db"
        SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{quote_plus(_user)}:{quote_plus(_pw)}@{_host}/{_db}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
