from flask import Blueprint, request, jsonify, render_template, current_app, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash

main = Blueprint("main", __name__)

# -------------------- Render Pages --------------------

@main.route("/")
def home():
    return render_template("register.html")

@main.route("/login_page")
def login_page():
    return render_template("login.html")

@main.route("/profile_page")
def profile_page():
    return render_template("profile.html")

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

# -------------------- User Login --------------------

@main.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user["password"], password):
            user.pop("password")
            session["user"] = user
            return jsonify({"message": "Login successful", "user": user}), 200
        else:
            return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

# -------------------- Daily Expense Chart API --------------------

@main.route("/api/daily_expenses")
def daily_expenses():
    user = session.get("user")
    if not user:
        return jsonify({"message": "Unauthorized"}), 401

    try:
        cursor = current_app.mysql.cursor(dictionary=True)
        cursor.execute("""
            SELECT DATE(date) AS day, SUM(amount) AS total
            FROM transactions
            WHERE account_id IN (
                SELECT id FROM accounts WHERE user_id = %s
            )
            AND type = 'Debit'
            AND MONTH(date) = MONTH(CURDATE())
            AND YEAR(date) = YEAR(CURDATE())
            GROUP BY DATE(date)
            ORDER BY DATE(date)
        """, (user["id"],))
        data = cursor.fetchall()
        cursor.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500

# -------------------- Logout --------------------

@main.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login_page")
