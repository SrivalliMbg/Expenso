from flask import Blueprint, request, jsonify, render_template, current_app, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from .totp_utils import TOTPManager

# ---------------- Blueprints ---------------- #
main = Blueprint("main", __name__)
chatbot_bp = Blueprint("chatbot_bp", __name__)

# -------------------- Render Pages -------------------- #

@main.route("/")
def home():
    return render_template("home.html")  # Dashboard page

@main.route("/dashboard")
def dashboard():
    return render_template("home.html")

@main.route("/login_page")
def login_page():
    return render_template("login.html")

@main.route("/register_page")
def register_page():
    return render_template("register.html")

@main.route("/profile_page")
def profile_page():
    return render_template("profile.html")

@main.route("/totp_setup_page")
def totp_setup_page():
    return render_template("totp_setup.html")

@main.route("/web_authenticator")
def web_authenticator():
    return render_template("web_authenticator.html")

@main.route("/accounts_page")
def accounts_page():
    return render_template("accounts.html", username="User")

@main.route("/expenses_page")
def expenses_page():
    return render_template("expenses.html", username="User")

@main.route("/cards_page")
def cards_page():
    return render_template("cards.html", username="User")

@main.route("/insurance_page")
def insurance_page():
    return render_template("insurance.html", username="User")

@main.route("/investments_page")
def investments_page():
    return render_template("investments.html", username="User")

@main.route("/recent_page")
def recent_page():
    return render_template("transactions.html", username="User")

@main.route("/transactions_page")
def transactions_page():
    return render_template("transactions.html", username="User")

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
        cursor.execute(
            """INSERT INTO users (username, email, password, status, dob, phone, profession)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (username, email, hashed_password, status, dob, phone, profession)
        )
        current_app.mysql.commit()
        cursor.close()
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

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
            return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

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
        return jsonify({"message": f"Error: {str(e)}"}), 500

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
        
        # Generate QR code
        qr_code = TOTPManager.generate_qr_code(secret, user["username"])
        
        return jsonify({
            "secret": secret,
            "qr_code": qr_code,
            "message": "TOTP setup data generated"
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

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
        return jsonify({"message": f"Error: {str(e)}"}), 500

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
        return jsonify({"message": f"Error: {str(e)}"}), 500

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
        return jsonify({"message": f"Error: {str(e)}"}), 500

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

@main.route('/api/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """Get financial summary for dashboard"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
        # Get total inflow (credit transactions) - no user_id filter needed
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_inflow
            FROM transactions
            WHERE type = 'Credit'
            AND MONTH(date) = MONTH(CURDATE())
            AND YEAR(date) = YEAR(CURDATE())
        """)
        inflow_result = cursor.fetchone()
        total_inflow = inflow_result['total_inflow'] if inflow_result else 0
        
        # Get total outflow (debit transactions) - no user_id filter needed
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_outflow
            FROM transactions
            WHERE type = 'Debit'
            AND MONTH(date) = MONTH(CURDATE())
            AND YEAR(date) = YEAR(CURDATE())
        """)
        outflow_result = cursor.fetchone()
        total_outflow = outflow_result['total_outflow'] if outflow_result else 0
        
        # Get spending by category from transactions table (your actual data)
        cursor.execute("""
            SELECT 
                COALESCE(category, 'Uncategorized') as category,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE type = 'Debit'
            AND MONTH(date) = MONTH(CURDATE())
            AND YEAR(date) = YEAR(CURDATE())
            GROUP BY category
            ORDER BY total_amount DESC
            LIMIT 5
        """)
        categories = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'inflow': float(total_inflow),
            'outflow': float(total_outflow),
            'categories': categories
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/dashboard/summary/<period>', methods=['GET'])
def get_dashboard_summary_by_period(period):
    """Get financial summary for dashboard with time period selection"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
        # Define date filters based on period
        if period == 'this_month':
            date_filter = "AND MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE())"
        elif period == 'last_month':
            date_filter = "AND MONTH(date) = MONTH(CURDATE() - INTERVAL 1 MONTH) AND YEAR(date) = YEAR(CURDATE() - INTERVAL 1 MONTH)"
        elif period == 'this_year':
            date_filter = "AND YEAR(date) = YEAR(CURDATE())"
        elif period == 'all_time':
            date_filter = ""
        else:
            date_filter = "AND MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE())"  # default to this month
        
        # Get total inflow (credit transactions)
        cursor.execute(f"""
            SELECT COALESCE(SUM(amount), 0) as total_inflow
            FROM transactions
            WHERE type = 'Credit'
            {date_filter}
        """)
        inflow_result = cursor.fetchone()
        total_inflow = inflow_result['total_inflow'] if inflow_result else 0
        
        # Get total outflow (debit transactions)
        cursor.execute(f"""
            SELECT COALESCE(SUM(amount), 0) as total_outflow
            FROM transactions
            WHERE type = 'Debit'
            {date_filter}
        """)
        outflow_result = cursor.fetchone()
        total_outflow = outflow_result['total_outflow'] if outflow_result else 0
        
        # Get spending by category from transactions table
        cursor.execute(f"""
            SELECT 
                COALESCE(category, 'Uncategorized') as category,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE type = 'Debit'
            {date_filter}
            GROUP BY category
            ORDER BY total_amount DESC
            LIMIT 5
        """)
        categories = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'inflow': float(total_inflow),
            'outflow': float(total_outflow),
            'categories': categories,
            'period': period
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/dashboard/transactions', methods=['GET'])
def get_recent_transactions():
    """Get recent transactions for dashboard"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
        # Get recent transactions - no user_id filter needed
        cursor.execute("""
            SELECT 
                title as description,
                amount,
                type,
                DATE_FORMAT(date, '%%d %%b') as formatted_date,
                date
            FROM transactions
            ORDER BY date DESC
            LIMIT 10
        """)
        transactions = cursor.fetchall()
        
        cursor.close()
        
        return jsonify({
            'transactions': transactions
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/dashboard/upcoming', methods=['GET'])
def get_upcoming_payments():
    """Get upcoming payments count"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
        # Count upcoming payments - no user_id filter needed
        cursor.execute("""
            SELECT COUNT(*) as upcoming_count
            FROM transactions
            WHERE date > CURDATE()
            AND type = 'Debit'
        """)
        result = cursor.fetchone()
        upcoming_count = result['upcoming_count'] if result else 0
        
        cursor.close()
        
        return jsonify({
            'upcoming_count': upcoming_count
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/dashboard/accounts', methods=['GET'])
def get_accounts_summary():
    """Get accounts summary for What I Have & What I Owe section"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
        # Get accounts with their balances
        cursor.execute("""
            SELECT id, type, bank, balance
            FROM accounts
        """)
        accounts = cursor.fetchall()
        
        # Get total loan amount
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_loans
            FROM loans
        """)
        loans_result = cursor.fetchone()
        loans_amount = float(loans_result['total_loans']) if loans_result else 0
        
        # Get total credit card limits
        cursor.execute("""
            SELECT COALESCE(SUM(limit_amount), 0) as total_cards
            FROM cards
        """)
        cards_result = cursor.fetchone()
        cards_amount = float(cards_result['total_cards']) if cards_result else 0
        
        # Calculate balances
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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

# -------------------- Accounts API -------------------- #
@main.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts from database"""
    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        
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
        return jsonify({"error": str(e)}), 500

@main.route('/api/accounts', methods=['POST'])
def add_account():
    """Add a new account to database"""
    try:
        data = request.json
        cursor = current_app.mysql.cursor()
        
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
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500
