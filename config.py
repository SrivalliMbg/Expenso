"""
Expenso configuration. All secrets must come from environment variables in production.
Set env vars or use .env (e.g. python-dotenv) — no hardcoded secrets.
Priority: DATABASE_URL has absolute priority when set; MYSQL_* are ignored for the
database connection in that case. Only when DATABASE_URL is unset do we use MYSQL_*.
No localhost default in production.
"""
import os
from urllib.parse import quote_plus, urlparse


def _env(key, default=""):
    """Read from environment; empty string if unset."""
    return os.environ.get(key, default).strip()


def _is_production():
    """True when FLASK_ENV is production or DEBUG is not enabled (no localhost default)."""
    env = (_env("FLASK_ENV") or "production").lower()
    debug = _env("DEBUG", "").lower() in ("true", "1", "yes")
    return env == "production" or not debug


def _normalize_database_url(raw_url):
    """
    Parse DATABASE_URL. Returns:
    - None if raw_url is empty/invalid
    - ("postgresql", sqlalchemy_uri) for postgres/postgresql (psycopg2)
    - ("mysql", host, user, password, db, sqlalchemy_uri) for mysql
    """
    if not raw_url or not raw_url.strip():
        return None
    raw = raw_url.strip()
    scheme = (raw.split(":")[0] or "").lower()
    # PostgreSQL: postgres:// -> postgresql:// for SQLAlchemy; use psycopg2
    if scheme in ("postgres", "postgresql"):
        url = raw
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if "://" in url and not url.split("://")[0].startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return ("postgresql", url)
    # MySQL: use only values from the URL (DATABASE_URL has priority; do not substitute from MYSQL_*)
    if "mysql" in scheme:
        try:
            parsed = urlparse(raw)
            host = parsed.hostname or ""
            port = parsed.port or 3306
            user = parsed.username or ""
            password = parsed.password or ""
            db = (parsed.path or "/").lstrip("/") or ""
            uri = f"mysql+mysqlconnector://{quote_plus(user or '')}:{quote_plus(password)}@{host or ''}:{port}/{db or ''}"
            return ("mysql", host or "", user or "", password, db or "", uri)
        except Exception:
            return None
    return None


# DATABASE_URL has absolute priority: when set, MYSQL_* are never used for the DB connection.
_raw_db_url = _env("DATABASE_URL")
_db_from_url = _normalize_database_url(_raw_db_url) if _raw_db_url else None

# Simple URI resolution: prefer DATABASE_URL (postgres:// -> postgresql://), else fall back to MySQL.
# SQLite: :memory: is overridden in create_app() with instance/local.db so tables persist.
db_url = os.getenv("DATABASE_URL", "").strip() or _raw_db_url
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    _sqlalchemy_database_uri = db_url
else:
    _sqlalchemy_database_uri = None  # set in Config from MySQL fallback

class Config:
    # Production: FLASK_ENV=production, DEBUG=False (Dockerfile / Render)
    FLASK_ENV = _env("FLASK_ENV") or "production"
    DEBUG = _env("DEBUG", "").lower() in ("true", "1", "yes")

    # Database: DATABASE_URL wins absolutely when set (MYSQL_* ignored); else fall back to MYSQL_*. No localhost default in production.
    if _db_from_url is not None:
        if _db_from_url[0] == "mysql":
            MYSQL_HOST = _db_from_url[1]
            MYSQL_USER = _db_from_url[2]
            MYSQL_PASSWORD = _db_from_url[3] or ""
            MYSQL_DB = _db_from_url[4]
        else:
            # PostgreSQL (Supabase): ignore MYSQL_*; no MySQL pool when DATABASE_URL is set
            MYSQL_HOST = ""
            MYSQL_USER = ""
            MYSQL_PASSWORD = ""
            MYSQL_DB = ""
    else:
        # DATABASE_URL not set: fall back to MYSQL_*; in production do not default to localhost
        if _is_production():
            MYSQL_HOST = _env("MYSQL_HOST")
            MYSQL_USER = _env("MYSQL_USER")
            MYSQL_PASSWORD = _env("MYSQL_PASSWORD") or ""
            MYSQL_DB = _env("MYSQL_DB")
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

    # SQLAlchemy: DATABASE_URL when set (postgres:// normalized to postgresql://); else fall back to MySQL
    if _sqlalchemy_database_uri is not None:
        SQLALCHEMY_DATABASE_URI = _sqlalchemy_database_uri
    else:
        if _is_production() and not _env("MYSQL_HOST"):
            SQLALCHEMY_DATABASE_URI = ""
        else:
            _pw = _env("MYSQL_PASSWORD") or ""
            _user = _env("MYSQL_USER") or "root"
            _host = _env("MYSQL_HOST") or "localhost"
            _db = _env("MYSQL_DB") or "expenso_db"
            SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{quote_plus(_user)}:{quote_plus(_pw)}@{_host}/{_db}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
