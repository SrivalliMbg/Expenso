from flask import Blueprint, request, jsonify, render_template, current_app, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from app.models.ingestion_models import db

main = Blueprint("main", __name__)

# -------------------- Render Pages --------------------

@main.route("/")
def home():
    return render_template("register.html")

@main.route("/login_page")
def login_page():
    return render_template("login.html")

@main.route("/home")
def dashboard():
    user = session.get("user")
    if not user:
        return redirect("/login_page")

    # Optional: fetch budget and total spent from another table
    user["budget"] = 10000  # Placeholder
    user["total_spent"] = 0  # Can be calculated dynamically

    return render_template("home.html", user=user)

# -------------------- User Registration --------------------

@main.route("/register", methods=["POST"], endpoint="register_post")
def register():
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
        db.session.execute(
            text("""INSERT INTO users (username, email, password, status, dob, phone, profession)
               VALUES (:username, :email, :password, :status, :dob, :phone, :profession)"""),
            {"username": username, "email": email, "password": hashed_password, "status": status, "dob": dob, "phone": phone, "profession": profession}
        )
        db.session.commit()
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error("Error: %s", e, exc_info=True)
        except Exception:
            pass
        return jsonify({"message": "Something went wrong. Please try again later."}), 500

# -------------------- User Login --------------------

@main.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    try:
        r = db.session.execute(text("SELECT * FROM users WHERE username = :username"), {"username": username})
        user_row = r.mappings().fetchone()
        user = dict(user_row) if user_row else None

        if user and check_password_hash(user["password"], password):
            user.pop("password")
            session["user"] = user
            return jsonify({"message": "Login successful", "user": user}), 200
        else:
            return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error("Error: %s", e, exc_info=True)
        except Exception:
            pass
        return jsonify({"message": "Something went wrong. Please try again later."}), 500

# -------------------- Daily Expense Chart API --------------------

@main.route("/api/daily_expenses")
def daily_expenses():
    user = session.get("user")
    if not user:
        return jsonify({"message": "Unauthorized"}), 401

    try:
        r = db.session.execute(text("""
            SELECT DATE(date) AS day, SUM(amount) AS total
            FROM transactions
            WHERE account_id IN (SELECT id FROM accounts WHERE user_id = :user_id)
            AND type = 'Debit'
            AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)
            GROUP BY DATE(date)
            ORDER BY DATE(date)
        """), {"user_id": user["id"]})
        data = [dict(row) for row in r.mappings().fetchall()]
        return jsonify(data), 200
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error("Error: %s", e, exc_info=True)
        except Exception:
            pass
        return jsonify({"message": "Something went wrong. Please try again later."}), 500

# -------------------- Logout --------------------

@main.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login_page")
