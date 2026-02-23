import re
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, current_app, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
from sqlalchemy import text
from .models.ingestion_models import db, ResetOTP
from .totp_utils import TOTPManager
from .forgot_otp import (
    generate_otp,
    hash_otp,
    verify_otp_hash,
    send_otp_email,
    send_otp_sms,
    create_reset_token,
    get_otp_expiry_minutes,
)
from .ocr_parser import (
    extract_text_from_image,
    extract_text_from_pdf,
    parse_financial_text,
    parse_policy_insurance_text,
    parse_investment_text,
)
from .mask_utils import mask_sensitive_data

# Email validation: reasonable format
def _is_valid_email(s):
    if not s or len(s) > 254:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, s))

# Phone validation: digits only, optional + at start, 10–15 digits
def _is_valid_phone(s):
    if not s:
        return False
    cleaned = s.strip().lstrip("+").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not cleaned.isdigit():
        return False
    return 10 <= len(cleaned) <= 15

# Safe error response: log real error server-side, never send SQL/details to the client
def _safe_error_response(e, user_message="Something went wrong. Please try again later."):
    try:
        current_app.logger.error("Server error: %s", e, exc_info=True)
    except Exception:
        pass  # if logger fails, at least don't crash
    return jsonify({"message": user_message, "error": user_message}), 500

# ---------------- Blueprints ---------------- #
main = Blueprint("main", __name__)
chatbot_bp = Blueprint("chatbot_bp", __name__)


def _db_available():
    """Database availability check using Flask-SQLAlchemy. Returns True if SELECT 1 succeeds."""
    try:
        db.session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _current_username():
    """Get the logged-in user's display name (from profile) for use in templates. Returns 'User' if not found."""
    user_id = session.get("user_id")
    if not user_id or not _db_available():
        return "User"
    try:
        result = db.session.execute(text("SELECT username FROM users WHERE id = :user_id"), {"user_id": user_id})
        row = result.mappings().fetchone()
        return (row.get("username") or "User") if row else "User"
    except Exception:
        return "User"


def _is_admin_user():
    """
    True if current user is admin: user_id == 1 (fallback) or users.is_admin = True.
    TODO: Replace with a proper role-based system (e.g. roles table or user.role) when available.
    """
    user_id = session.get("user_id")
    if not user_id:
        return False
    if user_id == 1:
        return True
    if not _db_available():
        return False
    try:
        result = db.session.execute(text("SELECT is_admin FROM users WHERE id = :user_id"), {"user_id": user_id})
        row = result.mappings().fetchone()
        return bool(row and row.get("is_admin"))
    except Exception:
        return False


def admin_required(f):
    """Restrict route to admin users. Redirect to login if not logged in; 403 if not admin."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("main.login_page"))
        if not _is_admin_user():
            if request.path.startswith("/api/"):
                return jsonify({"message": "Forbidden. Admin access required."}), 403
            return render_template("403.html", message="Admin access required.", username=_current_username()), 403
        return f(*args, **kwargs)
    return wrapped


# -------------------- Admin: seed user (synthetic data) -------------------- #
@main.route("/admin/seed-user", methods=["POST"])
@admin_required
def admin_seed_user():
    """
    Ensure the given user (or current user) has synthetic transaction data.
    Body (optional): { "user_id": 2 }. If omitted, seeds the logged-in user.
    """
    data = request.get_json(silent=True) or {}
    target_user_id = data.get("user_id") or session.get("user_id")
    if not target_user_id:
        return jsonify({"message": "user_id required or must be logged in"}), 400
    try:
        from app.utils.seed_user import ensure_user_has_synthetic_data
        action, count = ensure_user_has_synthetic_data(int(target_user_id))
        return jsonify({
            "message": "already_has_data" if action == "already_has_data" else "Synthetic data seeded.",
            "action": action,
            "count": count,
        }), 200
    except Exception as e:
        if current_app and getattr(current_app, "logger", None):
            current_app.logger.exception("admin_seed_user failed: %s", e)
        return jsonify({"message": "Seed failed.", "error": str(e)}), 500


# -------------------- Health (no auth, no DB) - for Render / load balancers -------------------- #
@main.route("/health")
def health():
    """Simple liveness check. No DB, no session. Use for Render or load balancer health checks."""
    return "App is running", 200


# -------------------- Render Pages -------------------- #

@main.route("/")
def home():
    if not session.get("user_id"):
        return redirect(url_for("main.login_page"))
    return render_template("home.html", username=_current_username())

@main.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("main.login_page"))
    return render_template("home.html", username=_current_username())

@main.route("/login_page")
def login_page():
    return render_template("login.html")

@main.route("/register_page")
def register_page():
    return render_template("register.html")

@main.route("/forgot_credentials_page")
def forgot_credentials_page():
    return render_template("forgot_credentials.html")

@main.route("/profile_edit_page")
def profile_edit_page():
    return render_template("profile_edit.html")

@main.route("/totp_setup_page")
def totp_setup_page():
    return render_template("totp_setup.html")

@main.route("/turing_test_page")
def turing_test_page():
    return render_template("turing_test.html")

@main.route("/web_authenticator")
def web_authenticator():
    return render_template("web_authenticator.html")

@main.route("/accounts_page")
def accounts_page():
    return render_template("accounts.html", username=_current_username())

@main.route("/expenses_page")
def expenses_page():
    return render_template("expenses.html", username=_current_username())

@main.route("/cards_page")
def cards_page():
    return render_template("cards.html", username=_current_username())

@main.route("/insurance_page")
def insurance_page():
    return render_template("insurance.html", username=_current_username())

@main.route("/investments_page")
def investments_page():
    return render_template("investments.html", username=_current_username())

@main.route("/recent_page")
def recent_page():
    return render_template("transactions.html", username=_current_username())

@main.route("/transactions_page")
def transactions_page():
    return render_template("transactions.html", username=_current_username())

# -------------------- Logout -------------------- #

@main.route("/logout_page")
def logout_page():
    """Show logout confirmation page"""
    return render_template("logout.html")

@main.route("/logout")
def logout():
    """Clear session and redirect to login"""
    session.clear()
    return redirect(url_for("main.login_page"))

@main.route("/error_page")
def error_page():
    return render_template("error.html")


# -------------------- Gmail OAuth (skeleton; no message reading) -------------------- #
@main.route("/api/gmail/oauth/start", methods=["GET"])
def gmail_oauth_start():
    """Redirect to Google OAuth consent. Scope: gmail.readonly. Requires login."""
    if not session.get("user_id"):
        return redirect(url_for("main.login_page"))
    try:
        from .gmail_oauth import initiate_google_oauth
        auth_url, state_or_error = initiate_google_oauth()
        if not auth_url:
            return jsonify({"message": state_or_error or "OAuth not configured"}), 503
        session["oauth_state"] = state_or_error
        return redirect(auth_url)
    except Exception as e:
        return _safe_error_response(e, "OAuth could not be started.")


@main.route("/api/gmail/oauth/callback", methods=["GET"])
def gmail_oauth_callback():
    """Handle Google redirect; exchange code for tokens and store encrypted. No message reading."""
    if not _db_available() or not session.get("user_id"):
        return redirect(url_for("main.login_page"))
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return redirect(url_for("main.dashboard"))
    try:
        from .gmail_oauth import store_oauth_tokens
        from google_auth_oauthlib.flow import Flow
        client_id = current_app.config.get("GOOGLE_CLIENT_ID")
        client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")
        redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI")
        flow = Flow.from_client_config(
            {"web": {"client_id": client_id, "client_secret": client_secret,
             "auth_uri": "https://accounts.google.com/o/oauth2/auth",
             "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [redirect_uri]}},
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=code)
        creds = flow.credentials
        expires_at = None
        if getattr(creds, "expiry", None):
            expires_at = creds.expiry
        store_oauth_tokens(
            session["user_id"],
            creds.token,
            getattr(creds, "refresh_token", None),
            expires_at,
            current_app,
        )
        session.pop("oauth_state", None)
    except Exception:
        pass
    return redirect(url_for("main.dashboard"))


# -------------------- User Registration -------------------- #
@main.route("/register", methods=["POST"], endpoint="register_post")
def register():
    if not _db_available():
        return jsonify({"message": "Database not available. Please check your database connection."}), 503

    data = request.json
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    status = data.get("status", "professional")
    dob = data.get("dob")
    phone = data.get("phone")
    profession = data.get("profession")

    hashed_password = generate_password_hash(password)

    try:
        # Check if username already exists
        r = db.session.execute(text("SELECT id FROM users WHERE username = :username"), {"username": username})
        if r.mappings().fetchone():
            return jsonify({"message": "Username already exists. Please choose a different username."}), 400

        # Check if email already exists
        r = db.session.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})
        if r.mappings().fetchone():
            return jsonify({"message": "Email already registered. Please use a different email or try logging in."}), 400

        # Check if phone already exists (normalize: digits only, like forgot-credentials)
        if phone:
            phone_normalized = re.sub(r"\D", "", str(phone).strip().lstrip("+"))
            if phone_normalized:
                r = db.session.execute(
                    text("SELECT id FROM users WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') = :pn"),
                    {"pn": phone_normalized}
                )
                if r.mappings().fetchone():
                    return jsonify({"message": "This phone number is already registered. Please use a different number or try logging in."}), 400

        db.session.execute(
            text("""INSERT INTO users (username, email, password, status, dob, phone, profession)
               VALUES (:username, :email, :password, :status, :dob, :phone, :profession)"""),
            {"username": username, "email": email, "password": hashed_password, "status": status, "dob": dob, "phone": phone, "profession": profession}
        )
        db.session.commit()
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        error_msg = str(e).lower()
        # Check for common database errors and return user-friendly messages
        if "duplicate" in error_msg or "unique" in error_msg:
            if "username" in error_msg:
                return jsonify({"message": "Username already exists. Please choose a different username."}), 400
            elif "email" in error_msg:
                return jsonify({"message": "Email already registered. Please use a different email or try logging in."}), 400
        # For other errors, use safe response but log the actual error
        return _safe_error_response(e, "Registration failed. Please check your information and try again.")

# -------------------- User Login -------------------- #
@main.route("/login", methods=["POST"])
def login():
    if not _db_available():
        return jsonify({"message": "Database not available. Please check your database connection."}), 503

    data = request.json
    raw_username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    totp_code = data.get("totp_code")  # Optional TOTP code
    # Normalize username like registration: lowercase, remove all whitespace (login form may send "Full Name")
    username = re.sub(r"\s+", "", raw_username.lower()) if raw_username else ""

    if not username or not password:
        return jsonify({"message": "Username and password are required."}), 400

    try:
        result = db.session.execute(text("SELECT * FROM users WHERE username = :username"), {"username": username})
        user_row = result.mappings().fetchone()
        user = dict(user_row) if user_row else None
        stored_hash = (user.get("password") or "") if user else ""
        if isinstance(stored_hash, bytes):
            stored_hash = stored_hash.decode("utf-8", errors="replace")
        else:
            stored_hash = str(stored_hash)

        if user and stored_hash and check_password_hash(stored_hash, password):
            # 2FA: if TOTP enabled, do not create session yet; return TOTP_REQUIRED
            two_factor = user.get("two_factor_enabled") or bool(user.get("totp_secret"))
            if two_factor:
                if not totp_code:
                    # Create short-lived token for TOTP verification step
                    totp_token = create_reset_token()
                    expires = datetime.utcnow() + timedelta(minutes=5)
                    try:
                        db.session.execute(
                            text("INSERT INTO pending_totp_verification (token, user_id, expires_at) VALUES (:token, :user_id, :expires_at)"),
                            {"token": totp_token, "user_id": user["id"], "expires_at": expires}
                        )
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        db.session.execute(text("""
                            CREATE TABLE IF NOT EXISTS pending_totp_verification (
                                token VARCHAR(64) PRIMARY KEY,
                                user_id INTEGER NOT NULL,
                                expires_at TIMESTAMP NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """))
                        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_expires ON pending_totp_verification (expires_at)"))
                        db.session.commit()
                        db.session.execute(
                            text("INSERT INTO pending_totp_verification (token, user_id, expires_at) VALUES (:token, :user_id, :expires_at)"),
                            {"token": totp_token, "user_id": user["id"], "expires_at": expires}
                        )
                        db.session.commit()
                    user_safe = {k: v for k, v in user.items() if k not in ("password", "totp_secret")}
                    return jsonify({
                        "status": "TOTP_REQUIRED",
                        "message": "TOTP code required",
                        "totp_verification_token": totp_token,
                        "user": user_safe
                    }), 200
                if not TOTPManager.verify_totp(user["totp_secret"], totp_code):
                    return jsonify({"message": "Invalid TOTP code"}), 401
            # Login successful (no 2FA or TOTP verified)
            user.pop("password", None)
            user.pop("totp_secret", None)
            session["user_id"] = user["id"]
            return jsonify({"message": "Login successful", "user": user}), 200
        else:
            return jsonify({"message": "Invalid username or password. Please check your credentials and try again."}), 401
    except Exception as e:
        return _safe_error_response(e, "Login failed. Please check your connection and try again.")


@main.route("/verify-totp", methods=["POST"])
def verify_totp():
    """
    Verify TOTP code after login when status was TOTP_REQUIRED.
    Body: { "totp_verification_token": "...", "totp_code": "123456" }.
    On success: create session and return user; never return totp_secret.
    """
    if not _db_available():
        return jsonify({"message": "Database not available."}), 503
    data = request.json or {}
    token = (data.get("totp_verification_token") or "").strip()
    totp_code = (data.get("totp_code") or "").strip()
    if not token or not totp_code:
        return jsonify({"message": "totp_verification_token and totp_code are required."}), 400
    try:
        result = db.session.execute(
            text("SELECT user_id, expires_at FROM pending_totp_verification WHERE token = :token"),
            {"token": token}
        )
        row = result.mappings().fetchone()
        if not row:
            return jsonify({"message": "Invalid or expired verification. Please log in again."}), 401
        exp = row["expires_at"]
        if exp and datetime.utcnow() > (exp.replace(tzinfo=None) if hasattr(exp, "replace") else exp):
            db.session.execute(text("DELETE FROM pending_totp_verification WHERE token = :token"), {"token": token})
            db.session.commit()
            return jsonify({"message": "Verification expired. Please log in again."}), 401
        user_id = row["user_id"]
        result = db.session.execute(
            text("SELECT id, username, email, status, dob, phone, profession, created_at FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user = result.mappings().fetchone()
        if not user:
            return jsonify({"message": "User not found."}), 404
        user = dict(user)
        secret = TOTPManager.get_user_totp_secret(user_id)
        if not secret or not TOTPManager.verify_totp(secret, totp_code):
            return jsonify({"message": "Invalid TOTP code."}), 401
        db.session.execute(text("DELETE FROM pending_totp_verification WHERE token = :token"), {"token": token})
        db.session.commit()
        session["user_id"] = user_id
        return jsonify({"message": "Login successful", "user": user}), 200
    except Exception as e:
        return _safe_error_response(e, "Verification failed. Please try again.")


# -------------------- Forgot credentials (OTP via email/phone) -------------------- #
@main.route("/api/forgot_credentials/send_otp", methods=["POST"])
def forgot_send_otp():
    """Send OTP to user's email or phone after verifying they exist."""
    if not _db_available():
        return jsonify({"message": "Database not available."}), 503
    data = request.json or {}
    channel = (data.get("channel") or "email").strip().lower()
    value = (data.get("value") or "").strip()
    if not value:
        return jsonify({"message": "Please enter your email or phone number."}), 400
    if channel not in ("email", "phone"):
        return jsonify({"message": "Choose either email or phone."}), 400
    if channel == "email":
        if not _is_valid_email(value):
            return jsonify({"message": "Please enter a valid email address."}), 400
    else:
        if not _is_valid_phone(value):
            return jsonify({"message": "Please enter a valid phone number (10–15 digits, with or without country code)."}), 400
    try:
        if channel == "email":
            result = db.session.execute(text("SELECT id, email FROM users WHERE email = :value"), {"value": value})
        else:
            phone_normalized = re.sub(r"\D", "", value.strip().lstrip("+"))
            result = db.session.execute(
                text("""SELECT id, phone FROM users WHERE
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') = :pn
                OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') = RIGHT(:pn, 10)
                OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') = RIGHT(:pn2, 11)
                LIMIT 1"""),
                {"pn": phone_normalized, "pn2": phone_normalized}
            )
        user = result.mappings().fetchone()
        if not user:
            return jsonify({"message": "No account found with this " + ("email" if channel == "email" else "phone number") + "."}), 404
        user_id = user["id"]
        identifier = value.lower() if channel == "email" else re.sub(r"\D", "", value.strip().lstrip("+"))
        window_mins = current_app.config.get("OTP_RATE_LIMIT_WINDOW_MINUTES", 10)
        limit_count = current_app.config.get("OTP_RATE_LIMIT_COUNT", 5)
        threshold = datetime.utcnow() - timedelta(minutes=window_mins)
        count = db.session.query(ResetOTP).filter(
            ResetOTP.identifier == identifier,
            ResetOTP.created_at > threshold
        ).count()
        if count >= limit_count:
            return jsonify({"message": f"Too many OTP requests. Try again after {window_mins} minutes."}), 429
        otp = generate_otp(6)
        expiry_mins = get_otp_expiry_minutes(current_app)
        expires_at = datetime.utcnow() + timedelta(minutes=expiry_mins)
        db.session.query(ResetOTP).filter(
            (ResetOTP.identifier == identifier) | (ResetOTP.user_id == user_id)
        ).delete(synchronize_session=False)
        db.session.add(ResetOTP(identifier=identifier, otp=otp, user_id=user_id, expires_at=expires_at))
        db.session.commit()
        sent = False
        if channel == "email":
            sent = send_otp_email(value, otp, current_app)
        else:
            sent = send_otp_sms(value, otp, current_app)
        if not sent:
            mail_configured = bool(
                current_app.config.get("MAIL_SERVER")
                and current_app.config.get("MAIL_USERNAME")
                and current_app.config.get("MAIL_PASSWORD")
            )
            sms_configured = bool(
                (current_app.config.get("TWILIO_ACCOUNT_SID")
                 and current_app.config.get("TWILIO_AUTH_TOKEN")
                 and current_app.config.get("TWILIO_FROM_NUMBER"))
                or current_app.config.get("SMS_WEB_API_URL")
            )
            if channel == "email" and not mail_configured:
                return jsonify({
                    "message": "OTP could not be sent: email is not configured on this server. Please contact the administrator or set up MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD in config."
                }), 503
            if channel == "phone" and not sms_configured:
                return jsonify({
                    "message": "OTP by phone/SMS is not set up. Use Email for OTP, or ask the administrator to configure Twilio (TWILIO_*) or a web SMS API (SMS_WEB_API_URL and optionally SMS_WEB_API_KEY) in .env."
                }), 503
            return jsonify({
                "message": "We could not send the OTP to your " + ("email" if channel == "email" else "phone") + ". Please try again later or contact support."
            }), 503
        return jsonify({"message": "OTP sent to your " + ("email" if channel == "email" else "phone") + ". Check your inbox."}), 200
    except Exception as e:
        return _safe_error_response(e, "Could not send OTP. Please try again.")

@main.route("/api/forgot_credentials/verify_otp", methods=["POST"])
def forgot_verify_otp():
    """Verify OTP and return a one-time reset token."""
    if not _db_available():
        return jsonify({"message": "Database not available."}), 503
    data = request.json or {}
    channel = (data.get("channel") or "email").strip().lower()
    value = (data.get("value") or "").strip()
    otp = (data.get("otp") or "").strip()
    if not value or not otp:
        return jsonify({"message": "Email/phone and OTP are required."}), 400
    try:
        identifier = value.lower() if channel == "email" else re.sub(r"\D", "", value.strip().lstrip("+"))
        row = db.session.query(ResetOTP).filter(ResetOTP.identifier == identifier).first()
        if not row:
            return jsonify({"message": "Invalid or expired OTP."}), 400
        stored = (row.otp or "").strip()
        if not stored:
            return jsonify({"message": "Invalid or expired OTP."}), 400
        if len(stored) == 64 and all(c in "0123456789abcdef" for c in stored.lower()):
            valid = verify_otp_hash(otp, stored)
        else:
            valid = (otp.strip() == stored)
        if not valid:
            return jsonify({"message": "Invalid or expired OTP."}), 400
        exp = row.expires_at
        if exp and datetime.utcnow() > (exp.replace(tzinfo=None) if hasattr(exp, "replace") else exp):
            db.session.delete(row)
            db.session.commit()
            return jsonify({"message": "OTP has expired. Please request a new one."}), 400
        reset_token = create_reset_token()
        row.reset_token = reset_token
        db.session.commit()
        return jsonify({"message": "Verified. You can now set a new password.", "reset_token": reset_token}), 200
    except Exception as e:
        return _safe_error_response(e, "Verification failed. Please try again.")

@main.route("/api/forgot_credentials/reset_password", methods=["POST"])
def forgot_reset_password():
    """Set new password using the reset token from verify_otp."""
    if not _db_available():
        return jsonify({"message": "Database not available."}), 503
    data = request.json or {}
    reset_token = (data.get("reset_token") or "").strip()
    new_password = data.get("new_password")
    if not reset_token:
        return jsonify({"message": "Reset token is required."}), 400
    if not new_password or len(new_password) < 6:
        return jsonify({"message": "Password must be at least 6 characters."}), 400
    try:
        row = db.session.query(ResetOTP).filter(ResetOTP.reset_token == reset_token).first()
        if not row:
            return jsonify({"message": "Invalid or expired reset link. Please start again from Forgot credentials."}), 400
        expires_at = row.expires_at
        if expires_at and datetime.utcnow() > (expires_at.replace(tzinfo=None) if hasattr(expires_at, "replace") else expires_at):
            db.session.delete(row)
            db.session.commit()
            return jsonify({"message": "Reset link has expired. Please request a new OTP."}), 400
        user_id = row.user_id
        hashed = generate_password_hash(new_password)
        db.session.execute(text("UPDATE users SET password = :password WHERE id = :user_id"), {"password": hashed, "user_id": user_id})
        db.session.delete(row)
        db.session.commit()
        return jsonify({"message": "Password updated successfully. You can now log in."}), 200
    except Exception as e:
        return _safe_error_response(e, "Could not update password. Please try again.")

# -------------------- Profile API -------------------- #
@main.route("/api/profile", methods=["GET"])
def get_profile():
    """Get current user's profile (for edit page and refresh)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401
    if not _db_available():
        return jsonify({"message": "Database not available"}), 503
    try:
        result = db.session.execute(
            text("SELECT id, username, email, status, dob, phone, profession, created_at FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user = result.mappings().fetchone()
        if not user:
            return jsonify({"message": "User not found"}), 404
        user = dict(user)
        if user.get("dob"):
            user["dob"] = user["dob"].isoformat() if hasattr(user["dob"], "isoformat") else str(user["dob"])
        return jsonify({"user": mask_sensitive_data(user)}), 200
    except Exception as e:
        return _safe_error_response(e)

def _do_update_profile():
    """Shared logic for profile update (used by both route paths)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401
    if not _db_available():
        return jsonify({"message": "Database not available"}), 503
    data = request.json
    if not data:
        return jsonify({"message": "No data provided"}), 400
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    status = data.get("status") or "professional"
    dob = data.get("dob")
    phone = (data.get("phone") or "").strip()
    profession = (data.get("profession") or "").strip()
    if not username:
        return jsonify({"message": "Name is required"}), 400
    if not email:
        return jsonify({"message": "Email is required"}), 400
    try:
        r = db.session.execute(text("SELECT id FROM users WHERE username = :username AND id != :user_id"), {"username": username, "user_id": user_id})
        if r.mappings().fetchone():
            return jsonify({"message": "That name is already taken by another account"}), 400
        r = db.session.execute(text("SELECT id FROM users WHERE email = :email AND id != :user_id"), {"email": email, "user_id": user_id})
        if r.mappings().fetchone():
            return jsonify({"message": "That email is already in use"}), 400
        db.session.execute(
            text("UPDATE users SET username = :username, email = :email, status = :status, dob = :dob, phone = :phone, profession = :profession WHERE id = :user_id"),
            {"username": username, "email": email, "status": status, "dob": dob or None, "phone": phone, "profession": profession, "user_id": user_id}
        )
        db.session.commit()
        result = db.session.execute(
            text("SELECT id, username, email, status, dob, phone, profession, created_at FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user = result.mappings().fetchone()
        if user:
            user = dict(user)
            if user.get("dob"):
                user["dob"] = user["dob"].isoformat() if hasattr(user["dob"], "isoformat") else str(user["dob"])
        return jsonify({"message": "Profile updated", "user": mask_sensitive_data(user or {})}), 200
    except Exception as e:
        return _safe_error_response(e)


@main.route("/api/profile/update", methods=["POST"])
def update_profile():
    """Update current user's profile (username, email, status, dob, phone, profession)."""
    return _do_update_profile()


@main.route("/api/profile-update", methods=["POST"])
def update_profile_alt():
    """Alternate URL for profile update (avoids 404 with some servers/proxies)."""
    return _do_update_profile()


# -------------------- Optional: Fetch All Users -------------------- #
@main.route("/users", methods=["GET"])
def get_users():
    try:
        result = db.session.execute(text("SELECT id, username, email, status, dob, phone, profession, created_at FROM users"))
        rows = result.mappings().fetchall()
        users = [dict(r) for r in rows]
        return jsonify(users), 200
    except Exception as e:
        return _safe_error_response(e)

# -------------------- TOTP Management -------------------- #
@main.route("/totp/setup", methods=["POST"])
def setup_totp():
    """Generate TOTP secret and QR code for user setup"""
    if not _db_available():
        return jsonify({"message": "Database not available"}), 503

    data = request.json
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"message": "User ID required"}), 400

    try:
        secret = TOTPManager.generate_secret()
        result = db.session.execute(text("SELECT username, email FROM users WHERE id = :user_id"), {"user_id": user_id})
        user = result.mappings().fetchone()
        if not user:
            return jsonify({"message": "User not found"}), 404
        user = dict(user)
        display_name = (user.get("email") or user.get("username") or str(user_id))
        qr_code = TOTPManager.generate_qr_code(secret, display_name)
        if not qr_code or not qr_code.startswith("data:image/"):
            return jsonify({"message": "QR code could not be generated"}), 500
        expires = datetime.utcnow() + timedelta(minutes=5)
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS totp_setup_pending (
                user_id INTEGER PRIMARY KEY, secret VARCHAR(64) NOT NULL,
                expires_at TIMESTAMP NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.execute(
            text("""
                INSERT INTO totp_setup_pending (user_id, secret, expires_at) VALUES (:user_id, :secret, :expires_at)
                ON CONFLICT (user_id) DO UPDATE SET secret = EXCLUDED.secret, expires_at = EXCLUDED.expires_at
            """),
            {"user_id": user_id, "secret": secret, "expires_at": expires}
        )
        db.session.commit()
        return jsonify({
            "qr_code": qr_code,
            "message": "TOTP setup data generated. Scan with Google Authenticator."
        }), 200

    except ValueError as e:
        return jsonify({"message": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("TOTP setup failed: %s", e)
        return _safe_error_response(e)

@main.route("/totp/verify", methods=["POST"])
def verify_totp_setup():
    """Verify TOTP code during setup and enable TOTP for user. Secret is read from server-side pending store."""
    if not _db_available():
        return jsonify({"message": "Database not available"}), 503
    data = request.json or {}
    user_id = data.get("user_id")
    totp_code = (data.get("totp_code") or "").strip()
    if not user_id or not totp_code:
        return jsonify({"message": "User ID and TOTP code required"}), 400
    try:
        result = db.session.execute(
            text("SELECT secret, expires_at FROM totp_setup_pending WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        row = result.mappings().fetchone()
        if not row:
            return jsonify({"message": "No pending TOTP setup. Start setup again."}), 400
        row = dict(row)
        exp = row["expires_at"]
        if exp and datetime.utcnow() > (exp.replace(tzinfo=None) if hasattr(exp, "replace") else exp):
            db.session.execute(text("DELETE FROM totp_setup_pending WHERE user_id = :user_id"), {"user_id": user_id})
            db.session.commit()
            return jsonify({"message": "Setup expired. Start TOTP setup again."}), 400
        secret = row["secret"]
        if not TOTPManager.verify_totp(secret, totp_code):
            return jsonify({"message": "Invalid TOTP code"}), 400
        if not TOTPManager.enable_totp(user_id, secret):
            return jsonify({"message": "Failed to enable TOTP"}), 500
        db.session.execute(text("DELETE FROM totp_setup_pending WHERE user_id = :user_id"), {"user_id": user_id})
        db.session.commit()
        return jsonify({"message": "TOTP enabled successfully"}), 200
    except Exception as e:
        return _safe_error_response(e)

@main.route("/totp/disable", methods=["POST"])
def disable_totp():
    """Disable TOTP for a user"""
    if not _db_available():
        return jsonify({"message": "Database not available"}), 503
    
    data = request.json
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"message": "User ID required"}), 400
    
    try:
        if TOTPManager.disable_totp(user_id):
            return jsonify({"message": "TOTP disabled successfully"}), 200
        else:
            return jsonify({"message": "Failed to disable TOTP"}), 500
            
    except Exception as e:
        return _safe_error_response(e)

@main.route("/totp/status", methods=["GET"])
def get_totp_status():
    """Get TOTP status for a user"""
    user_id = request.args.get("user_id")
    
    if not user_id:
        return jsonify({"message": "User ID required"}), 400
    
    try:
        is_enabled = TOTPManager.is_totp_enabled(user_id)
        return jsonify({"totp_enabled": is_enabled}), 200
        
    except Exception as e:
        return _safe_error_response(e)

# ---------------- API Endpoints (Chatbot & AI Features) ---------------- #
@chatbot_bp.route('/api/upload_data', methods=['POST'])
def upload_data():
    return jsonify({"message": "Data uploaded successfully"}), 200

@chatbot_bp.route('/api/guidance', methods=['POST'])
def get_guidance():
    return jsonify({"guidance": "Sample career advice"}), 200

@chatbot_bp.route('/api/budget', methods=['POST'])
def get_budget():
    return jsonify({"budget": "Sample budget insights"}), 200

@chatbot_bp.route('/api/insights', methods=['POST'])
def get_insights():
    return jsonify({"insights": "Sample financial insights"}), 200

# Chatbot endpoint is handled in financial_chatbot.py

# -------------------- Dashboard Data APIs -------------------- #

def _require_dashboard_user():
    """Return (user_id, None) if logged in, else (None, 401_json_response). Caller should return the response when not logged in."""
    user_id = session.get('user_id')
    if user_id:
        return user_id, None
    return None, (jsonify({"message": "Not logged in", "error": "Not logged in"}), 401)

def _dashboard_account_filter():
    """Return SQL fragment to restrict dashboard data to logged-in user (use with :user_id)."""
    return " AND account_id IN (SELECT id FROM accounts WHERE user_id = :user_id)"


def _date_range_this_month():
    """Return (start, end) as date objects for current month. end is first day of next month (exclusive). Database-agnostic."""
    today = date.today()
    start = today.replace(day=1)
    if today.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _date_range_last_month():
    """Return (start, end) for previous month. Database-agnostic."""
    today = date.today()
    if today.month == 1:
        start = today.replace(year=today.year - 1, month=12, day=1)
        end = today.replace(day=1)
    else:
        start = today.replace(month=today.month - 1, day=1)
        end = today.replace(day=1)
    return start, end


def _date_range_this_year():
    """Return (start, end) for current year. end is first day of next year."""
    today = date.today()
    start = today.replace(month=1, day=1)
    end = start.replace(year=start.year + 1)
    return start, end

@main.route('/api/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """Get financial summary for dashboard. Requires login."""
    user_id, err = _require_dashboard_user()
    if err is not None:
        return err
    try:
        acc_filter = _dashboard_account_filter()
        params = {"user_id": user_id}
        r = db.session.execute(text("""
            SELECT COALESCE(SUM(amount), 0) as total_inflow
            FROM transactions
            WHERE type = 'Credit'
            AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
            """ + acc_filter), params)
        inflow_result = r.mappings().fetchone()
        total_inflow = inflow_result["total_inflow"] if inflow_result else 0

        r = db.session.execute(text("""
            SELECT COALESCE(SUM(amount), 0) as total_outflow
            FROM transactions
            WHERE type = 'Debit'
            AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
            """ + acc_filter), params)
        outflow_result = r.mappings().fetchone()
        total_outflow = outflow_result["total_outflow"] if outflow_result else 0

        r = db.session.execute(text("""
            SELECT
                COALESCE(category, 'Uncategorized') as category,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE type = 'Debit'
            AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
            """ + acc_filter + """
            GROUP BY category
            ORDER BY total_amount DESC
            LIMIT 5
        """), params)
        categories = [dict(row) for row in r.mappings().fetchall()]

        total_inflow = 0 if total_inflow is None else float(total_inflow)
        total_outflow = 0 if total_outflow is None else float(total_outflow)
        return jsonify(mask_sensitive_data({
            'inflow': total_inflow,
            'outflow': total_outflow,
            'total': total_inflow - total_outflow,
            'most_spent_category': None,
            'categories': categories
        })), 200

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/dashboard/summary/<period>', methods=['GET'])
def get_dashboard_summary_by_period(period):
    """Get financial summary for dashboard with time period selection. Requires login."""
    user_id, err = _require_dashboard_user()
    if err is not None:
        return err
    try:
        acc_filter = _dashboard_account_filter()
        params = {"user_id": user_id}
        if period == 'this_month':
            date_filter = "AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)"
        elif period == 'last_month':
            date_filter = "AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE - INTERVAL '1 month') AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE - INTERVAL '1 month')"
        elif period == 'this_year':
            date_filter = "AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)"
        elif period == 'all_time':
            date_filter = ""
        else:
            date_filter = "AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)"

        r = db.session.execute(text("""
            SELECT COALESCE(SUM(amount), 0) as total_inflow
            FROM transactions WHERE type = 'Credit' """ + date_filter + acc_filter), params)
        inflow_result = r.mappings().fetchone()
        total_inflow = inflow_result["total_inflow"] if inflow_result else 0

        r = db.session.execute(text("""
            SELECT COALESCE(SUM(amount), 0) as total_outflow
            FROM transactions WHERE type = 'Debit' """ + date_filter + acc_filter), params)
        outflow_result = r.mappings().fetchone()
        total_outflow = outflow_result["total_outflow"] if outflow_result else 0

        r = db.session.execute(text("""
            SELECT COALESCE(category, 'Uncategorized') as category,
                COALESCE(SUM(amount), 0) as total_amount, COUNT(*) as transaction_count
            FROM transactions WHERE type = 'Debit' """ + date_filter + acc_filter + """
            GROUP BY category ORDER BY total_amount DESC LIMIT 5
        """), params)
        categories = [dict(row) for row in r.mappings().fetchall()]

        total = float(total_inflow or 0) - float(total_outflow or 0)
        most_spent_category = None
        if categories:
            top = max(categories, key=lambda c: float(c.get("total_amount") or 0))
            if top and float(top.get("total_amount") or 0) > 0:
                most_spent_category = top.get("category")

        return jsonify(mask_sensitive_data({
            'inflow': float(total_inflow or 0),
            'outflow': float(total_outflow or 0),
            'total': total,
            'most_spent_category': most_spent_category,
            'categories': categories,
            'period': period
        })), 200

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/dashboard/transactions', methods=['GET'])
def get_recent_transactions():
    """Get recent transactions for dashboard. Requires login."""
    user_id, err = _require_dashboard_user()
    if err is not None:
        return err
    try:
        acc_filter = _dashboard_account_filter()
        r = db.session.execute(text("""
            SELECT title as description, amount, type,
                TO_CHAR(date, 'DD Mon') as formatted_date, date
            FROM transactions WHERE 1=1 """ + acc_filter + """
            ORDER BY date DESC LIMIT 10
        """), {"user_id": user_id})
        transactions = [dict(row) for row in r.mappings().fetchall()]

        return jsonify(mask_sensitive_data({'transactions': transactions})), 200

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/dashboard/upcoming', methods=['GET'])
def get_upcoming_payments():
    """Get upcoming payments count. Requires login."""
    user_id, err = _require_dashboard_user()
    if err is not None:
        return err
    try:
        acc_filter = _dashboard_account_filter()
        r = db.session.execute(text("""
            SELECT COUNT(*) as upcoming_count
            FROM transactions WHERE date > CURRENT_DATE AND type = 'Debit' """ + acc_filter),
            {"user_id": user_id})
        result = r.mappings().fetchone()
        upcoming_count = result["upcoming_count"] if result else 0
        upcoming_count = 0 if upcoming_count is None else int(upcoming_count)

        return jsonify(mask_sensitive_data({'upcoming_count': upcoming_count})), 200

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/dashboard/accounts', methods=['GET'])
def get_accounts_summary():
    """Get accounts summary for What I Have & What I Owe section. Requires login."""
    user_id, err = _require_dashboard_user()
    if err is not None:
        return err
    try:
        if user_id:
            r = db.session.execute(text("SELECT id, type, bank, balance FROM accounts WHERE user_id = :user_id"), {"user_id": user_id})
            accounts = [dict(row) for row in r.mappings().fetchall()]
        else:
            accounts = []

        account_ids = [a["id"] for a in accounts] if accounts else []
        if account_ids:
            from sqlalchemy import bindparam
            stmt_loans = text("SELECT COALESCE(SUM(amount), 0) as total_loans FROM loans WHERE account_id IN :ids").bindparams(bindparam("ids", expanding=True))
            loans_result = db.session.execute(stmt_loans, {"ids": account_ids}).mappings().fetchone()
        else:
            loans_result = {"total_loans": 0}
        loans_amount = float(loans_result["total_loans"]) if loans_result else 0

        if account_ids:
            from sqlalchemy import bindparam
            stmt_cards = text("SELECT COALESCE(SUM(limit_amount), 0) as total_cards FROM cards WHERE account_id IN :ids").bindparams(bindparam("ids", expanding=True))
            cards_result = db.session.execute(stmt_cards, {"ids": account_ids}).mappings().fetchone()
        else:
            cards_result = {"total_cards": 0}
        cards_amount = float(cards_result["total_cards"]) if cards_result else 0

        savings_balance = 0
        credit_balance = 0
        for account in (accounts or []):
            balance = float(account.get("balance", 0) or 0)
            account_type = (account.get("type") or "").lower()
            if account_type == "savings":
                savings_balance += balance
            elif account_type == "credit":
                credit_balance += balance

        payload = {
            "accounts": accounts or [],
            "savings_balance": savings_balance if savings_balance is not None else 0,
            "credit_balance": credit_balance if credit_balance is not None else 0,
            "cards_amount": float(cards_amount) if cards_amount is not None else 0,
            "loans_amount": float(loans_amount) if loans_amount is not None else 0
        }
        return jsonify(mask_sensitive_data(payload)), 200

    except Exception as e:
        return _safe_error_response(e)

# -------------------- Cards API -------------------- #
@main.route('/api/cards', methods=['GET'])
def get_cards():
    """Get all cards from database"""
    try:
        r = db.session.execute(text("""
            SELECT id, account_id, card_type, card_number, expiry_date, cvv, limit_amount, created_at
            FROM cards ORDER BY created_at DESC
        """))
        cards = [dict(row) for row in r.mappings().fetchall()]

        return jsonify({
            'cards': cards
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/cards', methods=['POST'])
def add_card():
    """Add a new card to database"""
    try:
        data = request.json
        db.session.execute(text("""
            INSERT INTO cards (account_id, card_type, card_number, expiry_date, cvv, limit_amount)
            VALUES (:account_id, :card_type, :card_number, :expiry_date, :cvv, :limit_amount)
        """), {
            "account_id": data.get("account_id"),
            "card_type": data.get("card_type"),
            "card_number": data.get("card_number"),
            "expiry_date": data.get("expiry_date"),
            "cvv": data.get("cvv"),
            "limit_amount": data.get("limit_amount", 0)
        })
        db.session.commit()
        return jsonify({"message": "Card added successfully"}), 201

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/cards/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    """Delete a card from database"""
    try:
        result = db.session.execute(text("DELETE FROM cards WHERE id = :card_id"), {"card_id": card_id})
        if result.rowcount == 0:
            return jsonify({"error": "Card not found"}), 404
        db.session.commit()
        return jsonify({"message": "Card deleted successfully"}), 200

    except Exception as e:
        return _safe_error_response(e)

# -------------------- Insurance API -------------------- #
@main.route('/api/insurance', methods=['GET'])
def get_insurance():
    """Get all insurance policies from database"""
    try:
        r = db.session.execute(text("""
            SELECT id, account_id, policy_name, policy_type, premium_amount, coverage_amount, next_due_date, created_at
            FROM insurance ORDER BY created_at DESC
        """))
        insurance = [dict(row) for row in r.mappings().fetchall()]
        return jsonify({"insurance": insurance}), 200

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/insurance', methods=['POST'])
def add_insurance():
    """Add a new insurance policy to database"""
    try:
        data = request.json
        db.session.execute(text("""
            INSERT INTO insurance (account_id, policy_name, policy_type, premium_amount, coverage_amount, next_due_date)
            VALUES (:account_id, :policy_name, :policy_type, :premium_amount, :coverage_amount, :next_due_date)
        """), {
            "account_id": data.get("account_id"),
            "policy_name": data.get("policy_name"),
            "policy_type": data.get("policy_type"),
            "premium_amount": data.get("premium_amount"),
            "coverage_amount": data.get("coverage_amount"),
            "next_due_date": data.get("next_due_date")
        })
        db.session.commit()
        return jsonify({"message": "Insurance policy added successfully"}), 201

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/insurance/<int:policy_id>', methods=['DELETE'])
def delete_insurance(policy_id):
    """Delete an insurance policy from database"""
    try:
        result = db.session.execute(text("DELETE FROM insurance WHERE id = :policy_id"), {"policy_id": policy_id})
        if result.rowcount == 0:
            return jsonify({"error": "Insurance policy not found"}), 404
        db.session.commit()
        return jsonify({"message": "Insurance policy deleted successfully"}), 200

    except Exception as e:
        return _safe_error_response(e)

# -------------------- Investments API -------------------- #
@main.route('/api/investments', methods=['GET'])
def get_investments():
    """Get all investments from database"""
    try:
        r = db.session.execute(text("""
            SELECT id, account_id, investment_type, amount, start_date, maturity_date, created_at
            FROM investments ORDER BY created_at DESC
        """))
        investments = [dict(row) for row in r.mappings().fetchall()]
        return jsonify({"investments": investments}), 200

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/investments', methods=['POST'])
def add_investment():
    """Add a new investment to database"""
    try:
        data = request.json
        db.session.execute(text("""
            INSERT INTO investments (account_id, investment_type, amount, start_date, maturity_date)
            VALUES (:account_id, :investment_type, :amount, :start_date, :maturity_date)
        """), {
            "account_id": data.get("account_id"),
            "investment_type": data.get("investment_type"),
            "amount": data.get("amount"),
            "start_date": data.get("start_date"),
            "maturity_date": data.get("maturity_date")
        })
        db.session.commit()
        return jsonify({"message": "Investment added successfully"}), 201

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/investments/<int:investment_id>', methods=['DELETE'])
def delete_investment(investment_id):
    """Delete an investment from database"""
    try:
        result = db.session.execute(text("DELETE FROM investments WHERE id = :investment_id"), {"investment_id": investment_id})
        if result.rowcount == 0:
            return jsonify({"error": "Investment not found"}), 404
        db.session.commit()
        return jsonify({"message": "Investment deleted successfully"}), 200

    except Exception as e:
        return _safe_error_response(e)

# -------------------- Accounts API -------------------- #
@main.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts from database (for current user when logged in)"""
    try:
        user_id = session.get("user_id")
        if user_id:
            r = db.session.execute(text("""
                SELECT id, type, bank, branch, acc_no, balance, created_at
                FROM accounts WHERE user_id = :user_id ORDER BY created_at DESC
            """), {"user_id": user_id})
        else:
            r = db.session.execute(text("""
                SELECT id, type, bank, branch, acc_no, balance, created_at
                FROM accounts ORDER BY created_at DESC
            """))
        accounts = [dict(row) for row in r.mappings().fetchall()]
        return jsonify({"accounts": accounts}), 200

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/accounts', methods=['POST'])
def add_account():
    """Add a new account to database"""
    try:
        data = request.json
        user_id = session.get("user_id")
        if user_id:
            db.session.execute(text("""
                INSERT INTO accounts (user_id, type, bank, branch, acc_no, balance)
                VALUES (:user_id, :type, :bank, :branch, :acc_no, :balance)
            """), {
                "user_id": user_id,
                "type": data.get("type"),
                "bank": data.get("bank"),
                "branch": data.get("branch"),
                "acc_no": data.get("acc_no"),
                "balance": data.get("balance", 0)
            })
        else:
            db.session.execute(text("""
                INSERT INTO accounts (type, bank, branch, acc_no, balance)
                VALUES (:type, :bank, :branch, :acc_no, :balance)
            """), {
                "type": data.get("type"),
                "bank": data.get("bank"),
                "branch": data.get("branch"),
                "acc_no": data.get("acc_no"),
                "balance": data.get("balance", 0)
            })
        db.session.commit()
        return jsonify({"message": "Account added successfully"}), 201

    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete an account from database"""
    try:
        result = db.session.execute(text("DELETE FROM accounts WHERE id = :account_id"), {"account_id": account_id})
        if result.rowcount == 0:
            return jsonify({"error": "Account not found"}), 404
        db.session.commit()
        return jsonify({"message": "Account deleted successfully"}), 200

    except Exception as e:
        return _safe_error_response(e)


# -------------------- OCR / Message & Email Parser -------------------- #
# Internal/admin-only tool. Not shown in main UI; direct URL and API protected by @admin_required.

@main.route("/ocr_import_page")
@admin_required
def ocr_import_page():
    """Page to paste message/email text or upload image for parsing and import. Admin only."""
    return render_template("ocr_import.html", username=_current_username())


def _ocr_extract_text_from_file(f):
    """Extract text from uploaded file (image or PDF)."""
    if not f or not f.filename:
        return ""
    data = f.read()
    fn = (f.filename or "").lower()
    if fn.endswith(".pdf"):
        return extract_text_from_pdf(data)
    return extract_text_from_image(data)


@main.route("/api/ocr/parse", methods=["POST"])
@admin_required
def ocr_parse():
    """
    Parse message/email text, image, or PDF for financial data. Admin only.
    Body: JSON { "text": "..." } or form-data with "file" (image or PDF) or "text".
    Returns { "entries": [...], "policies": [...], "investments": [...], "raw_text": "..." if file }.
    """
    try:
        text = ""
        if request.is_json:
            text = (request.json or {}).get("text") or ""
        else:
            if "file" in request.files:
                f = request.files["file"]
                if f.filename:
                    text = _ocr_extract_text_from_file(f)
            if not text and "text" in request.form:
                text = request.form["text"] or ""
        text = (text or "").strip()
        entries = parse_financial_text(text)
        policies = parse_policy_insurance_text(text)
        investments = parse_investment_text(text)
        out = {"entries": entries, "policies": policies, "investments": investments}
        if request.is_json and request.json and request.json.get("text"):
            pass
        elif text and "file" in (request.files or {}):
            out["raw_text"] = text[:3000]
        return jsonify(out), 200
    except Exception as e:
        return _safe_error_response(e, "Failed to parse text, image, or PDF.")


@main.route("/api/ocr/import", methods=["POST"])
@admin_required
def ocr_import():
    """
    Import parsed entries, policies, and investments. Admin only.
    Body: { "account_id": optional, "entries": [...], "policies": [...], "investments": [...] }.
    Uses first account of current user if account_id not provided.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401
    if not _db_available():
        return jsonify({"message": "Database not available"}), 503
    data = request.json
    if not data:
        return jsonify({"message": "No data provided"}), 400
    entries = data.get("entries") or []
    policies = data.get("policies") or []
    investments = data.get("investments") or []
    if not entries and not policies and not investments:
        return jsonify({"message": "Nothing to import."}), 400
    account_id = data.get("account_id")
    try:
        if account_id is None or (entries and not account_id):
            r = db.session.execute(text("SELECT id FROM accounts WHERE user_id = :user_id ORDER BY id LIMIT 1"), {"user_id": user_id})
            row = r.mappings().fetchone()
            if not row:
                return jsonify({"message": "No account found. Add an account first."}), 400
            account_id = row["id"]
        else:
            r = db.session.execute(text("SELECT id FROM accounts WHERE id = :account_id AND user_id = :user_id"), {"account_id": account_id, "user_id": user_id})
            if not r.mappings().fetchone():
                return jsonify({"message": "Account not found"}), 404
        imported_txn = 0
        imported_policies = 0
        imported_inv = 0
        for e in entries:
            title = (e.get("title") or "Imported").strip()[:255]
            amount = float(e.get("amount") or 0)
            txn_type = (e.get("type") or "Debit").strip()[:20]
            date_val = e.get("date")
            category = (e.get("category") or "Other").strip()[:64]
            if not date_val:
                date_val = datetime.now().strftime("%Y-%m-%d")
            if isinstance(date_val, str) and len(date_val) > 10:
                date_val = date_val[:10]
            try:
                db.session.execute(
                    text("INSERT INTO transactions (account_id, title, amount, type, date, category) VALUES (:account_id, :title, :amount, :type, :date_val, :category)"),
                    {"account_id": account_id, "title": title, "amount": amount, "type": txn_type, "date_val": date_val, "category": category}
                )
                imported_txn += 1
                if txn_type.lower() == "debit":
                    db.session.execute(
                        text("INSERT INTO expenses (account_id, title, amount, category, date) VALUES (:account_id, :title, :amount, :category, :date_val)"),
                        {"account_id": account_id, "title": title, "amount": amount, "category": category, "date_val": date_val}
                    )
            except Exception as ex:
                if current_app and getattr(current_app, "logger", None):
                    current_app.logger.warning("OCR import skip row: %s", ex)
        for p in policies:
            try:
                db.session.execute(
                    text("""INSERT INTO insurance (account_id, policy_name, policy_type, premium_amount, coverage_amount, next_due_date)
                           VALUES (:account_id, :policy_name, :policy_type, :premium_amount, :coverage_amount, :next_due_date)"""),
                    {
                        "account_id": account_id,
                        "policy_name": (p.get("policy_name") or "Imported policy").strip()[:255],
                        "policy_type": (p.get("policy_type") or "Other").strip()[:64],
                        "premium_amount": float(p.get("premium_amount") or 0),
                        "coverage_amount": float(p.get("coverage_amount") or 0),
                        "next_due_date": (p.get("next_due_date") or "")[:10] or None,
                    }
                )
                imported_policies += 1
            except Exception as ex:
                if current_app and getattr(current_app, "logger", None):
                    current_app.logger.warning("OCR import policy skip: %s", ex)
        for inv in investments:
            try:
                db.session.execute(
                    text("""INSERT INTO investments (account_id, investment_type, amount, start_date, maturity_date)
                           VALUES (:account_id, :investment_type, :amount, :start_date, :maturity_date)"""),
                    {
                        "account_id": account_id,
                        "investment_type": (inv.get("investment_type") or "Other").strip()[:64],
                        "amount": float(inv.get("amount") or 0),
                        "start_date": (inv.get("start_date") or "")[:10] or None,
                        "maturity_date": (inv.get("maturity_date") or "")[:10] or None,
                    }
                )
                imported_inv += 1
            except Exception as ex:
                if current_app and getattr(current_app, "logger", None):
                    current_app.logger.warning("OCR import investment skip: %s", ex)
        db.session.commit()
        msg_parts = []
        if imported_txn:
            msg_parts.append(f"{imported_txn} transaction(s)")
        if imported_policies:
            msg_parts.append(f"{imported_policies} policy/policies")
        if imported_inv:
            msg_parts.append(f"{imported_inv} investment(s)")
        return jsonify({
            "message": "Imported " + (", ".join(msg_parts) or "0 items") + ".",
            "imported": imported_txn + imported_policies + imported_inv,
            "imported_txn": imported_txn,
            "imported_policies": imported_policies,
            "imported_inv": imported_inv,
        }), 200
    except Exception as e:
        return _safe_error_response(e, "Import failed. Please try again.")
