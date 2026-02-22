"""
Gmail OAuth skeleton. Redirects user to Google OAuth consent; stores encrypted tokens in DB.
Scope: gmail.readonly. Message reading is NOT implemented — secure OAuth flow only.
All secrets from environment: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, OAUTH_ENCRYPTION_KEY.
"""
import os
import base64
from flask import redirect, url_for, current_app, session
from functools import wraps

# Optional: use google-auth and google-auth-oauthlib when installed
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    _google_available = True
except ImportError:
    _google_available = False

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def _encryption_key(app):
    """32-byte key for simple XOR/encryption; in production use proper KMS or Fernet."""
    key = (app.config.get("OAUTH_ENCRYPTION_KEY") or os.environ.get("OAUTH_ENCRYPTION_KEY") or "").encode("utf-8")
    if len(key) < 32:
        key = (key * 32)[:32]
    return key[:32]


def _simple_encrypt(plaintext, key):
    """Simple XOR cipher for token storage. Replace with Fernet/KMS in production."""
    if not plaintext or not key:
        return None
    b = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    k = key if isinstance(key, bytes) else key.encode("utf-8")
    out = bytearray()
    for i, c in enumerate(b):
        out.append(c ^ k[i % len(k)])
    return base64.b64encode(bytes(out)).decode("ascii")


def _simple_decrypt(ciphertext, key):
    """Decrypt token. Use same algorithm as _simple_encrypt."""
    if not ciphertext or not key:
        return None
    try:
        b = base64.b64decode(ciphertext.encode("ascii"))
    except Exception:
        return None
    k = key if isinstance(key, bytes) else key.encode("utf-8")
    out = bytearray()
    for i, c in enumerate(b):
        out.append(c ^ k[i % len(k)])
    return out.decode("utf-8", errors="replace")


def initiate_google_oauth():
    """
    Redirect user to Google OAuth consent screen.
    Scopes: gmail.readonly. No message reading implemented.
    """
    if not _google_available:
        return None, "Google OAuth libraries not installed (pip install google-auth google-auth-oauthlib)"
    client_id = current_app.config.get("GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI") or os.environ.get("GOOGLE_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        return None, "Gmail OAuth not configured (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)"
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=[GMAIL_READONLY_SCOPE],
    )
    flow.redirect_uri = redirect_uri
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url, state


def store_oauth_tokens(user_id, access_token, refresh_token, expires_at, mysql_conn, app):
    """Store encrypted access_token and refresh_token in DB. Table: oauth_tokens."""
    key = _encryption_key(app)
    enc_access = _simple_encrypt(access_token, key)
    enc_refresh = _simple_encrypt(refresh_token, key) if refresh_token else None
    cursor = mysql_conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            user_id INT PRIMARY KEY,
            provider VARCHAR(32) NOT NULL DEFAULT 'google',
            access_token_encrypted TEXT,
            refresh_token_encrypted TEXT,
            expires_at DATETIME,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        """REPLACE INTO oauth_tokens (user_id, provider, access_token_encrypted, refresh_token_encrypted, expires_at)
           VALUES (%s, 'google', %s, %s, %s)""",
        (user_id, enc_access, enc_refresh, expires_at)
    )
    mysql_conn.commit()
    cursor.close()


def get_oauth_tokens(user_id, mysql_conn, app):
    """Retrieve and decrypt tokens for user. Returns (access_token, refresh_token) or (None, None)."""
    key = _encryption_key(app)
    cursor = mysql_conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT access_token_encrypted, refresh_token_encrypted FROM oauth_tokens WHERE user_id = %s AND provider = 'google'",
        (user_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    if not row:
        return None, None
    access = _simple_decrypt(row.get("access_token_encrypted"), key)
    refresh = _simple_decrypt(row.get("refresh_token_encrypted"), key)
    return access, refresh
