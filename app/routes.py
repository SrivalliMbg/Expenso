import re
from flask import Blueprint, request, jsonify, render_template, current_app, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from .totp_utils import TOTPManager
from .forgot_otp import (
    generate_otp,
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


def _current_username():
    """Get the logged-in user's display name (from profile) for use in templates. Returns 'User' if not found."""
    user_id = session.get("user_id")
    if not user_id or not current_app.mysql:
        return "User"
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        return (row.get("username") or "User") if row else "User"
    except Exception:
        return "User"


# -------------------- Render Pages -------------------- #

@main.route("/")
def home():
    return render_template("home.html", username=_current_username())

@main.route("/dashboard")
def dashboard():
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

# -------------------- User Registration -------------------- #
@main.route("/register", methods=["POST"], endpoint="register_post")
def register():
    if not current_app.mysql:
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
        cursor = current_app.mysql.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            return jsonify({"message": "Username already exists. Please choose a different username."}), 400
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            return jsonify({"message": "Email already registered. Please use a different email or try logging in."}), 400
        
        # Check if phone already exists (normalize: digits only, like forgot-credentials)
        if phone:
            phone_normalized = re.sub(r"\D", "", str(phone).strip().lstrip("+"))
            if phone_normalized:
                cursor.execute(
                    """SELECT id FROM users WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') = %s""",
                    (phone_normalized,)
                )
                if cursor.fetchone():
                    cursor.close()
                    return jsonify({"message": "This phone number is already registered. Please use a different number or try logging in."}), 400
        
        cursor.execute(
            """INSERT INTO users (username, email, password, status, dob, phone, profession)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (username, email, hashed_password, status, dob, phone, profession)
        )
        current_app.mysql.commit()
        cursor.close()
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
    if not current_app.mysql:
        return jsonify({"message": "Database not available. Please check your database connection."}), 503
    
    data = request.json
    username = data.get("username")
    password = data.get("password")
    totp_code = data.get("totp_code")  # Optional TOTP code

    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user["password"], password):
            # Check if TOTP is enabled for this user
            if user.get("totp_secret"):
                # TOTP is enabled, verify the code
                if not totp_code:
                    return jsonify({
                        "message": "TOTP code required", 
                        "requires_totp": True,
                        "user_id": user["id"]
                    }), 200
                
                if not TOTPManager.verify_totp(user["totp_secret"], totp_code):
                    return jsonify({"message": "Invalid TOTP code"}), 401
            
            # Login successful
            user.pop("password")  # remove sensitive info
            user.pop("totp_secret")  # remove TOTP secret from response
            session["user_id"] = user["id"]
            return jsonify({"message": "Login successful", "user": user}), 200
        else:
            return jsonify({"message": "Invalid username or password. Please check your credentials and try again."}), 401
    except Exception as e:
        return _safe_error_response(e, "Login failed. Please check your connection and try again.")

# -------------------- Forgot credentials (OTP via email/phone) -------------------- #
@main.route("/api/forgot_credentials/send_otp", methods=["POST"])
def forgot_send_otp():
    """Send OTP to user's email or phone after verifying they exist."""
    if not current_app.mysql:
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
        cursor = current_app.mysql.cursor(dictionary=True)
        if channel == "email":
            cursor.execute("SELECT id, email FROM users WHERE email = %s", (value,))
        else:
            phone_normalized = re.sub(r"\D", "", value.strip().lstrip("+"))
            # Match both: full number (e.g. 919876543210) and local-only (e.g. 9876543210) so accounts registered with or without country code are found
            cursor.execute(
                """SELECT id, phone FROM users WHERE 
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') = %s
                OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') = RIGHT(%s, 10)
                OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') = RIGHT(%s, 11)
                LIMIT 1""",
                (phone_normalized, phone_normalized, phone_normalized)
            )
        user = cursor.fetchone()
        if not user:
            cursor.close()
            return jsonify({"message": "No account found with this " + ("email" if channel == "email" else "phone number") + "."}), 404
        user_id = user["id"]
        otp = generate_otp(6)
        expires_at = datetime.utcnow() + timedelta(minutes=get_otp_expiry_minutes())
        identifier = value.lower() if channel == "email" else re.sub(r"\D", "", value.strip().lstrip("+"))
        # Ensure table exists (optional: run migration_reset_otp.sql)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reset_otps (
                id INT AUTO_INCREMENT PRIMARY KEY,
                identifier VARCHAR(255) NOT NULL,
                otp VARCHAR(10) NOT NULL,
                user_id INT NOT NULL,
                expires_at DATETIME NOT NULL,
                reset_token VARCHAR(64) NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_identifier (identifier),
                INDEX idx_reset_token (reset_token),
                INDEX idx_expires (expires_at)
            )
        """)
        cursor.execute(
            "DELETE FROM reset_otps WHERE identifier = %s OR user_id = %s",
            (identifier, user_id)
        )
        cursor.execute(
            "INSERT INTO reset_otps (identifier, otp, user_id, expires_at) VALUES (%s, %s, %s, %s)",
            (identifier, otp, user_id, expires_at)
        )
        current_app.mysql.commit()
        sent = False
        if channel == "email":
            sent = send_otp_email(value, otp, current_app)
        else:
            sent = send_otp_sms(value, otp, current_app)
        cursor.close()
        if not sent:
            mail_configured = bool(
                current_app.config.get("MAIL_SERVER")
                and current_app.config.get("MAIL_USERNAME")
                and current_app.config.get("MAIL_PASSWORD")
            )
            sms_configured = bool(
                current_app.config.get("TWILIO_ACCOUNT_SID")
                and current_app.config.get("TWILIO_AUTH_TOKEN")
                and current_app.config.get("TWILIO_FROM_NUMBER")
            )
            if channel == "email" and not mail_configured:
                return jsonify({
                    "message": "OTP could not be sent: email is not configured on this server. Please contact the administrator or set up MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD in config."
                }), 503
            if channel == "phone" and not sms_configured:
                return jsonify({
                    "message": "OTP by phone/SMS is not set up on this server. Please use Email to receive the OTP, or ask the administrator to configure Twilio (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER) in config."
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
    if not current_app.mysql:
        return jsonify({"message": "Database not available."}), 503
    data = request.json or {}
    channel = (data.get("channel") or "email").strip().lower()
    value = (data.get("value") or "").strip()
    otp = (data.get("otp") or "").strip()
    if not value or not otp:
        return jsonify({"message": "Email/phone and OTP are required."}), 400
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        identifier = value.lower() if channel == "email" else re.sub(r"\D", "", value.strip().lstrip("+"))
        cursor.execute(
            "SELECT id, user_id, expires_at FROM reset_otps WHERE identifier = %s AND otp = %s",
            (identifier, otp)
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return jsonify({"message": "Invalid or expired OTP."}), 400
        exp = row["expires_at"]
        if exp and datetime.utcnow() > (exp.replace(tzinfo=None) if hasattr(exp, "replace") else exp):
            cursor.execute("DELETE FROM reset_otps WHERE identifier = %s", (identifier,))
            current_app.mysql.commit()
            cursor.close()
            return jsonify({"message": "OTP has expired. Please request a new one."}), 400
        reset_token = create_reset_token()
        cursor.execute(
            "UPDATE reset_otps SET reset_token = %s WHERE id = %s",
            (reset_token, row["id"])
        )
        current_app.mysql.commit()
        cursor.close()
        return jsonify({"message": "Verified. You can now set a new password.", "reset_token": reset_token}), 200
    except Exception as e:
        return _safe_error_response(e, "Verification failed. Please try again.")

@main.route("/api/forgot_credentials/reset_password", methods=["POST"])
def forgot_reset_password():
    """Set new password using the reset token from verify_otp."""
    if not current_app.mysql:
        return jsonify({"message": "Database not available."}), 503
    data = request.json or {}
    reset_token = (data.get("reset_token") or "").strip()
    new_password = data.get("new_password")
    if not reset_token:
        return jsonify({"message": "Reset token is required."}), 400
    if not new_password or len(new_password) < 6:
        return jsonify({"message": "Password must be at least 6 characters."}), 400
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, expires_at FROM reset_otps WHERE reset_token = %s",
            (reset_token,)
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            return jsonify({"message": "Invalid or expired reset link. Please start again from Forgot credentials."}), 400
        expires_at = row["expires_at"]
        if expires_at and datetime.utcnow() > (expires_at.replace(tzinfo=None) if hasattr(expires_at, "replace") else expires_at):
            cursor.execute("DELETE FROM reset_otps WHERE reset_token = %s", (reset_token,))
            current_app.mysql.commit()
            cursor.close()
            return jsonify({"message": "Reset link has expired. Please request a new OTP."}), 400
        user_id = row["user_id"]
        hashed = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, user_id))
        cursor.execute("DELETE FROM reset_otps WHERE reset_token = %s", (reset_token,))
        current_app.mysql.commit()
        cursor.close()
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
    if not current_app.mysql:
        return jsonify({"message": "Database not available"}), 503
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute(
            """SELECT id, username, email, status, dob, phone, profession, created_at
               FROM users WHERE id = %s""",
            (user_id,)
        )
        user = cursor.fetchone()
        cursor.close()
        if not user:
            return jsonify({"message": "User not found"}), 404
        if user.get("dob"):
            user["dob"] = user["dob"].isoformat() if hasattr(user["dob"], "isoformat") else str(user["dob"])
        return jsonify({"user": user}), 200
    except Exception as e:
        return _safe_error_response(e)

def _do_update_profile():
    """Shared logic for profile update (used by both route paths)."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401
    if not current_app.mysql:
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
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (username, user_id))
        if cursor.fetchone():
            cursor.close()
            return jsonify({"message": "That name is already taken by another account"}), 400
        cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
        if cursor.fetchone():
            cursor.close()
            return jsonify({"message": "That email is already in use"}), 400
        cursor.execute(
            """UPDATE users SET username = %s, email = %s, status = %s, dob = %s, phone = %s, profession = %s
               WHERE id = %s""",
            (username, email, status, dob or None, phone, profession, user_id)
        )
        current_app.mysql.commit()
        cursor.execute(
            """SELECT id, username, email, status, dob, phone, profession, created_at FROM users WHERE id = %s""",
            (user_id,)
        )
        user = cursor.fetchone()
        cursor.close()
        if user and user.get("dob"):
            user["dob"] = user["dob"].isoformat() if hasattr(user["dob"], "isoformat") else str(user["dob"])
        return jsonify({"message": "Profile updated", "user": user}), 200
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
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute(
            """SELECT id, username, email, status, dob, phone, profession, created_at
               FROM users"""
        )
        users = cursor.fetchall()
        cursor.close()
        return jsonify(users), 200
    except Exception as e:
        return _safe_error_response(e)

# -------------------- TOTP Management -------------------- #
@main.route("/totp/setup", methods=["POST"])
def setup_totp():
    """Generate TOTP secret and QR code for user setup"""
    if not current_app.mysql:
        return jsonify({"message": "Database not available"}), 503
    
    data = request.json
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"message": "User ID required"}), 400
    
    try:
        # Generate new TOTP secret
        secret = TOTPManager.generate_secret()
        
        # Get user info for QR code
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        # Generate QR code (requires Pillow for PNG)
        qr_code = TOTPManager.generate_qr_code(secret, user["username"])
        if not qr_code or not qr_code.startswith("data:image/"):
            return jsonify({"message": "QR code could not be generated"}), 500
        
        return jsonify({
            "secret": secret,
            "qr_code": qr_code,
            "message": "TOTP setup data generated"
        }), 200
        
    except ValueError as e:
        return jsonify({"message": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("TOTP setup failed: %s", e)
        return _safe_error_response(e)

@main.route("/totp/verify", methods=["POST"])
def verify_totp_setup():
    """Verify TOTP code during setup and enable TOTP for user"""
    if not current_app.mysql:
        return jsonify({"message": "Database not available"}), 503
    
    data = request.json
    user_id = data.get("user_id")
    secret = data.get("secret")
    totp_code = data.get("totp_code")
    
    if not all([user_id, secret, totp_code]):
        return jsonify({"message": "User ID, secret, and TOTP code required"}), 400
    
    try:
        # Verify the TOTP code
        if not TOTPManager.verify_totp(secret, totp_code):
            return jsonify({"message": "Invalid TOTP code"}), 400
        
        # Enable TOTP for the user
        if TOTPManager.enable_totp(user_id, secret):
            return jsonify({"message": "TOTP enabled successfully"}), 200
        else:
            return jsonify({"message": "Failed to enable TOTP"}), 500
            
    except Exception as e:
        return _safe_error_response(e)

@main.route("/totp/disable", methods=["POST"])
def disable_totp():
    """Disable TOTP for a user"""
    if not current_app.mysql:
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

def _dashboard_user_filters():
    """Return SQL fragment and params to restrict dashboard data to logged-in user (by account_id -> accounts.user_id)."""
    user_id = session.get('user_id')
    if user_id:
        return " AND account_id IN (SELECT id FROM accounts WHERE user_id = %s)", (user_id,)
    return "", ()

@main.route('/api/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """Get financial summary for dashboard"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        account_filter, acc_params = _dashboard_user_filters()
        
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_inflow
            FROM transactions
            WHERE type = 'Credit'
            AND MONTH(date) = MONTH(CURDATE())
            AND YEAR(date) = YEAR(CURDATE())
            """ + account_filter, acc_params)
        inflow_result = cursor.fetchone()
        total_inflow = inflow_result['total_inflow'] if inflow_result else 0
        
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_outflow
            FROM transactions
            WHERE type = 'Debit'
            AND MONTH(date) = MONTH(CURDATE())
            AND YEAR(date) = YEAR(CURDATE())
            """ + account_filter, acc_params)
        outflow_result = cursor.fetchone()
        total_outflow = outflow_result['total_outflow'] if outflow_result else 0
        
        cursor.execute("""
            SELECT 
                COALESCE(category, 'Uncategorized') as category,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE type = 'Debit'
            AND MONTH(date) = MONTH(CURDATE())
            AND YEAR(date) = YEAR(CURDATE())
            """ + account_filter + """
            GROUP BY category
            ORDER BY total_amount DESC
            LIMIT 5
        """, acc_params)
        categories = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'inflow': float(total_inflow),
            'outflow': float(total_outflow),
            'categories': categories
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/dashboard/summary/<period>', methods=['GET'])
def get_dashboard_summary_by_period(period):
    """Get financial summary for dashboard with time period selection"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        account_filter, acc_params = _dashboard_user_filters()
        
        if period == 'this_month':
            date_filter = "AND MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE())"
        elif period == 'last_month':
            date_filter = "AND MONTH(date) = MONTH(CURDATE() - INTERVAL 1 MONTH) AND YEAR(date) = YEAR(CURDATE() - INTERVAL 1 MONTH)"
        elif period == 'this_year':
            date_filter = "AND YEAR(date) = YEAR(CURDATE())"
        elif period == 'all_time':
            date_filter = ""
        else:
            date_filter = "AND MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE())"
        
        cursor.execute(f"""
            SELECT COALESCE(SUM(amount), 0) as total_inflow
            FROM transactions
            WHERE type = 'Credit'
            {date_filter}
            {account_filter}
        """, acc_params)
        inflow_result = cursor.fetchone()
        total_inflow = inflow_result['total_inflow'] if inflow_result else 0
        
        cursor.execute(f"""
            SELECT COALESCE(SUM(amount), 0) as total_outflow
            FROM transactions
            WHERE type = 'Debit'
            {date_filter}
            {account_filter}
        """, acc_params)
        outflow_result = cursor.fetchone()
        total_outflow = outflow_result['total_outflow'] if outflow_result else 0
        
        cursor.execute(f"""
            SELECT 
                COALESCE(category, 'Uncategorized') as category,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE type = 'Debit'
            {date_filter}
            {account_filter}
            GROUP BY category
            ORDER BY total_amount DESC
            LIMIT 5
        """, acc_params)
        categories = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'inflow': float(total_inflow),
            'outflow': float(total_outflow),
            'categories': categories,
            'period': period
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/dashboard/transactions', methods=['GET'])
def get_recent_transactions():
    """Get recent transactions for dashboard"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        account_filter, acc_params = _dashboard_user_filters()
        
        cursor.execute("""
            SELECT 
                title as description,
                amount,
                type,
                DATE_FORMAT(date, '%%d %%b') as formatted_date,
                date
            FROM transactions
            WHERE 1=1
            """ + account_filter + """
            ORDER BY date DESC
            LIMIT 10
        """, acc_params)
        transactions = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'transactions': transactions
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/dashboard/upcoming', methods=['GET'])
def get_upcoming_payments():
    """Get upcoming payments count"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        account_filter, acc_params = _dashboard_user_filters()
        
        cursor.execute("""
            SELECT COUNT(*) as upcoming_count
            FROM transactions
            WHERE date > CURDATE()
            AND type = 'Debit'
            """ + account_filter, acc_params)
        result = cursor.fetchone()
        upcoming_count = result['upcoming_count'] if result else 0
        
        cursor.close()
        
        return jsonify({
            'upcoming_count': upcoming_count
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/dashboard/accounts', methods=['GET'])
def get_accounts_summary():
    """Get accounts summary for What I Have & What I Owe section"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        user_id = session.get('user_id')
        
        if user_id:
            cursor.execute("""
                SELECT id, type, bank, balance
                FROM accounts
                WHERE user_id = %s
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, type, bank, balance
                FROM accounts
            """)
        accounts = cursor.fetchall()
        
        account_ids = [a['id'] for a in accounts] if accounts else []
        if account_ids:
            placeholders = ','.join(['%s'] * len(account_ids))
            cursor.execute(f"""
                SELECT COALESCE(SUM(amount), 0) as total_loans
                FROM loans
                WHERE account_id IN ({placeholders})
            """, account_ids)
        else:
            cursor.execute("SELECT 0 as total_loans")
        loans_result = cursor.fetchone()
        loans_amount = float(loans_result['total_loans']) if loans_result else 0
        
        if account_ids:
            placeholders = ','.join(['%s'] * len(account_ids))
            cursor.execute(f"""
                SELECT COALESCE(SUM(limit_amount), 0) as total_cards
                FROM cards
                WHERE account_id IN ({placeholders})
            """, account_ids)
        else:
            cursor.execute("SELECT 0 as total_cards")
        cards_result = cursor.fetchone()
        cards_amount = float(cards_result['total_cards']) if cards_result else 0
        
        savings_balance = 0
        credit_balance = 0
        for account in accounts:
            balance = float(account.get('balance', 0))
            account_type = account.get('type', '').lower()
            if account_type == 'savings':
                savings_balance += balance
            elif account_type == 'credit':
                credit_balance += balance
        
        cursor.close()
        
        return jsonify({
            'savings_balance': savings_balance,
            'credit_balance': credit_balance,
            'cards_amount': cards_amount,
            'loans_amount': loans_amount
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

# -------------------- Cards API -------------------- #
@main.route('/api/cards', methods=['GET'])
def get_cards():
    """Get all cards from database"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, account_id, card_type, card_number, expiry_date, cvv, limit_amount, created_at
            FROM cards
            ORDER BY created_at DESC
        """)
        cards = cursor.fetchall()
        
        cursor.close()
        
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
        cursor = current_app.mysql.cursor()
        
        cursor.execute("""
            INSERT INTO cards (account_id, card_type, card_number, expiry_date, cvv, limit_amount)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data.get('account_id'),
            data.get('card_type'),
            data.get('card_number'),
            data.get('expiry_date'),
            data.get('cvv'),
            data.get('limit_amount', 0)
        ))
        
        current_app.mysql.commit()
        cursor.close()
        
        return jsonify({"message": "Card added successfully"}), 201
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/cards/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    """Delete a card from database"""
    try:
        cursor = current_app.mysql.cursor()
        
        cursor.execute("DELETE FROM cards WHERE id = %s", (card_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Card not found"}), 404
        
        current_app.mysql.commit()
        cursor.close()
        
        return jsonify({"message": "Card deleted successfully"}), 200
        
    except Exception as e:
        return _safe_error_response(e)

# -------------------- Insurance API -------------------- #
@main.route('/api/insurance', methods=['GET'])
def get_insurance():
    """Get all insurance policies from database"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, account_id, policy_name, policy_type, premium_amount, coverage_amount, next_due_date, created_at
            FROM insurance
            ORDER BY created_at DESC
        """)
        insurance = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'insurance': insurance
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/insurance', methods=['POST'])
def add_insurance():
    """Add a new insurance policy to database"""
    try:
        data = request.json
        cursor = current_app.mysql.cursor()
        
        cursor.execute("""
            INSERT INTO insurance (account_id, policy_name, policy_type, premium_amount, coverage_amount, next_due_date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data.get('account_id'),
            data.get('policy_name'),
            data.get('policy_type'),
            data.get('premium_amount'),
            data.get('coverage_amount'),
            data.get('next_due_date')
        ))
        
        current_app.mysql.commit()
        cursor.close()
        
        return jsonify({"message": "Insurance policy added successfully"}), 201
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/insurance/<int:policy_id>', methods=['DELETE'])
def delete_insurance(policy_id):
    """Delete an insurance policy from database"""
    try:
        cursor = current_app.mysql.cursor()
        
        cursor.execute("DELETE FROM insurance WHERE id = %s", (policy_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Insurance policy not found"}), 404
        
        current_app.mysql.commit()
        cursor.close()
        
        return jsonify({"message": "Insurance policy deleted successfully"}), 200
        
    except Exception as e:
        return _safe_error_response(e)

# -------------------- Investments API -------------------- #
@main.route('/api/investments', methods=['GET'])
def get_investments():
    """Get all investments from database"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, account_id, investment_type, amount, start_date, maturity_date, created_at
            FROM investments
            ORDER BY created_at DESC
        """)
        investments = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'investments': investments
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/investments', methods=['POST'])
def add_investment():
    """Add a new investment to database"""
    try:
        data = request.json
        cursor = current_app.mysql.cursor()
        
        cursor.execute("""
            INSERT INTO investments (account_id, investment_type, amount, start_date, maturity_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            data.get('account_id'),
            data.get('investment_type'),
            data.get('amount'),
            data.get('start_date'),
            data.get('maturity_date')
        ))
        
        current_app.mysql.commit()
        cursor.close()
        
        return jsonify({"message": "Investment added successfully"}), 201
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/investments/<int:investment_id>', methods=['DELETE'])
def delete_investment(investment_id):
    """Delete an investment from database"""
    try:
        cursor = current_app.mysql.cursor()
        
        cursor.execute("DELETE FROM investments WHERE id = %s", (investment_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Investment not found"}), 404
        
        current_app.mysql.commit()
        cursor.close()
        
        return jsonify({"message": "Investment deleted successfully"}), 200
        
    except Exception as e:
        return _safe_error_response(e)

# -------------------- Accounts API -------------------- #
@main.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts from database (for current user when logged in)"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        user_id = session.get('user_id')
        
        if user_id:
            cursor.execute("""
                SELECT id, type, bank, branch, acc_no, balance, created_at
                FROM accounts
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, type, bank, branch, acc_no, balance, created_at
                FROM accounts
                ORDER BY created_at DESC
            """)
        accounts = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'accounts': accounts
        }), 200
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/accounts', methods=['POST'])
def add_account():
    """Add a new account to database"""
    try:
        data = request.json
        cursor = current_app.mysql.cursor()
        user_id = session.get('user_id')
        
        if user_id:
            cursor.execute("""
                INSERT INTO accounts (user_id, type, bank, branch, acc_no, balance)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                data.get('type'),
                data.get('bank'),
                data.get('branch'),
                data.get('acc_no'),
                data.get('balance', 0)
            ))
        else:
            cursor.execute("""
                INSERT INTO accounts (type, bank, branch, acc_no, balance)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                data.get('type'),
                data.get('bank'),
                data.get('branch'),
                data.get('acc_no'),
                data.get('balance', 0)
            ))
        
        current_app.mysql.commit()
        cursor.close()
        
        return jsonify({"message": "Account added successfully"}), 201
        
    except Exception as e:
        return _safe_error_response(e)

@main.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete an account from database"""
    try:
        cursor = current_app.mysql.cursor()
        
        cursor.execute("DELETE FROM accounts WHERE id = %s", (account_id,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Account not found"}), 404
        
        current_app.mysql.commit()
        cursor.close()
        
        return jsonify({"message": "Account deleted successfully"}), 200
        
    except Exception as e:
        return _safe_error_response(e)


# -------------------- OCR / Message & Email Parser -------------------- #
@main.route("/ocr_import_page")
def ocr_import_page():
    """Page to paste message/email text or upload image for parsing and import."""
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
def ocr_parse():
    """
    Parse message/email text, image, or PDF for financial data.
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
def ocr_import():
    """
    Import parsed entries, policies, and investments.
    Body: { "account_id": optional, "entries": [...], "policies": [...], "investments": [...] }.
    Uses first account of current user if account_id not provided.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"message": "Not logged in"}), 401
    if not current_app.mysql:
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
        cursor = current_app.mysql.cursor(dictionary=True)
        if account_id is None or (entries and not account_id):
            cursor.execute("SELECT id FROM accounts WHERE user_id = %s ORDER BY id LIMIT 1", (user_id,))
            row = cursor.fetchone()
            if not row:
                cursor.close()
                return jsonify({"message": "No account found. Add an account first."}), 400
            account_id = row["id"]
        else:
            cursor.execute("SELECT id FROM accounts WHERE id = %s AND user_id = %s", (account_id, user_id))
            if not cursor.fetchone():
                cursor.close()
                return jsonify({"message": "Account not found"}), 404
        cursor.close()
        cursor = current_app.mysql.cursor()
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
                cursor.execute(
                    """INSERT INTO transactions (account_id, title, amount, type, date, category)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (account_id, title, amount, txn_type, date_val, category)
                )
                imported_txn += 1
                if txn_type.lower() == "debit":
                    cursor.execute(
                        """INSERT INTO expenses (account_id, title, amount, category, date)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (account_id, title, amount, category, date_val)
                    )
            except Exception as ex:
                if current_app and getattr(current_app, "logger", None):
                    current_app.logger.warning("OCR import skip row: %s", ex)
        for p in policies:
            try:
                cursor.execute(
                    """INSERT INTO insurance (account_id, policy_name, policy_type, premium_amount, coverage_amount, next_due_date)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        account_id,
                        (p.get("policy_name") or "Imported policy").strip()[:255],
                        (p.get("policy_type") or "Other").strip()[:64],
                        float(p.get("premium_amount") or 0),
                        float(p.get("coverage_amount") or 0),
                        (p.get("next_due_date") or "")[:10] or None,
                    )
                )
                imported_policies += 1
            except Exception as ex:
                if current_app and getattr(current_app, "logger", None):
                    current_app.logger.warning("OCR import policy skip: %s", ex)
        for inv in investments:
            try:
                cursor.execute(
                    """INSERT INTO investments (account_id, investment_type, amount, start_date, maturity_date)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        account_id,
                        (inv.get("investment_type") or "Other").strip()[:64],
                        float(inv.get("amount") or 0),
                        (inv.get("start_date") or "")[:10] or None,
                        (inv.get("maturity_date") or "")[:10] or None,
                    )
                )
                imported_inv += 1
            except Exception as ex:
                if current_app and getattr(current_app, "logger", None):
                    current_app.logger.warning("OCR import investment skip: %s", ex)
        current_app.mysql.commit()
        cursor.close()
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
