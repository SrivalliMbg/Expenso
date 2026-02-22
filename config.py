"""
Expenso configuration. All secrets must come from environment variables in production.
Set env vars or use .env (e.g. python-dotenv) — no hardcoded secrets.
Supports DATABASE_URL (PostgreSQL/Supabase or MySQL) or fallback to MYSQL_* for local development.
"""
import os
from urllib.parse import quote_plus, urlparse


def _env(key, default=""):
    """Read from environment; empty string if unset."""
    return os.environ.get(key, default).strip()


def _normalize_database_url():
    """
    Parse DATABASE_URL. Returns:
    - None if DATABASE_URL not set
    - ("postgresql", sqlalchemy_uri) for postgres/postgresql (psycopg2)
    - ("mysql", host, user, password, db, sqlalchemy_uri) for mysql
    """
    raw = _env("DATABASE_URL")
    if not raw:
        return None
    scheme = (raw.split(":")[0] or "").lower()
    # PostgreSQL: postgres:// -> postgresql:// for SQLAlchemy; use psycopg2 driver
    if scheme in ("postgres", "postgresql"):
        url = raw
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if "://" in url and not url.split("://")[0].startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return ("postgresql", url)
    # MySQL: existing behavior for MYSQL_* and mysql+mysqlconnector URI (no hardcoded defaults)
    if "mysql" in scheme:
        try:
            parsed = urlparse(raw)
            host = parsed.hostname or _env("MYSQL_HOST")
            port = parsed.port or 3306
            user = parsed.username or _env("MYSQL_USER")
            password = parsed.password or ""
            db = (parsed.path or "/").lstrip("/") or _env("MYSQL_DB")
            uri = f"mysql+mysqlconnector://{quote_plus(user or '')}:{quote_plus(password)}@{host or ''}:{port}/{db or ''}"
            return ("mysql", host or "", user or "", password, db or "", uri)
        except Exception:
            return None
    return None


_db_from_url = _normalize_database_url()

class Config:
    # Production: FLASK_ENV=production, DEBUG=False (Dockerfile / Render)
    FLASK_ENV = _env("FLASK_ENV") or "production"
    DEBUG = _env("DEBUG", "").lower() in ("true", "1", "yes")

    # Database: DATABASE_URL (PostgreSQL or MySQL) or fallback to MYSQL_* for local
    if _db_from_url is None:
        MYSQL_HOST = _env("MYSQL_HOST") or "localhost"
        MYSQL_USER = _env("MYSQL_USER") or "root"
        MYSQL_PASSWORD = _env("MYSQL_PASSWORD") or ""
        MYSQL_DB = _env("MYSQL_DB") or "expenso_db"
    elif _db_from_url[0] == "mysql":
        MYSQL_HOST = _db_from_url[1]
        MYSQL_USER = _db_from_url[2]
        MYSQL_PASSWORD = _db_from_url[3] or ""
        MYSQL_DB = _db_from_url[4]
    else:
        # PostgreSQL (Supabase): MYSQL_* left from env for any legacy reads
        MYSQL_HOST = _env("MYSQL_HOST") or ""
        MYSQL_USER = _env("MYSQL_USER") or ""
        MYSQL_PASSWORD = _env("MYSQL_PASSWORD") or ""
        MYSQL_DB = _env("MYSQL_DB") or ""

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

    # SQLAlchemy (ingestion models); PostgreSQL or MySQL from DATABASE_URL or MYSQL_*
    if _db_from_url is None:
        _pw = _env("MYSQL_PASSWORD") or ""
        _user = _env("MYSQL_USER") or "root"
        _host = _env("MYSQL_HOST") or "localhost"
        _db = _env("MYSQL_DB") or "expenso_db"
        SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{quote_plus(_user)}:{quote_plus(_pw)}@{_host}/{_db}"
    elif _db_from_url[0] == "postgresql":
        SQLALCHEMY_DATABASE_URI = _db_from_url[1]
    else:
        SQLALCHEMY_DATABASE_URI = _db_from_url[5]
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
