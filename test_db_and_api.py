"""
Run from project root: python test_db_and_api.py
Tests (1) MySQL transactions table structure and sample data, (2) dashboard API endpoints.
"""
import sys

# --- 1) MySQL: transactions table structure and sample data ---
print("=== MySQL: TRANSACTIONS TABLE ===")
try:
    import mysql.connector
    from config import Config

    connection = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB,
    )
    cursor = connection.cursor(dictionary=True)

    print("Structure:")
    cursor.execute("DESCRIBE transactions")
    for col in cursor.fetchall():
        print(f"  {col['Field']}: {col['Type']}")

    print("\nSample data (LIMIT 3):")
    cursor.execute("SELECT * FROM transactions LIMIT 3")
    rows = cursor.fetchall()
    for row in rows:
        print(f"  {row}")
    if not rows:
        print("  (no rows)")

    cursor.close()
    connection.close()
except Exception as e:
    print(f"MySQL Error: {e}")
    sys.exit(1)

# --- 2) Dashboard API (app must be running on 127.0.0.1:5000) ---
print("\n=== Dashboard API (requires server running) ===")
try:
    import requests
    import json

    base_url = "http://127.0.0.1:5000"

    # Summary (try base summary first; some apps use /api/dashboard/summary/this_month)
    for path in ["/api/dashboard/summary", "/api/dashboard/summary/this_month"]:
        try:
            r = requests.get(f"{base_url}{path}", timeout=5)
            print(f"GET {path} -> {r.status_code}")
            if r.status_code == 200:
                print(f"  Data: {json.dumps(r.json(), indent=2)[:500]}...")
            else:
                print(f"  Body: {r.text[:200]}")
        except Exception as e:
            print(f"  Error: {e}")

    # Accounts
    try:
        r = requests.get(f"{base_url}/api/dashboard/accounts", timeout=5)
        print(f"GET /api/dashboard/accounts -> {r.status_code}")
        if r.status_code == 200:
            print(f"  Data: {json.dumps(r.json(), indent=2)[:500]}...")
        else:
            print(f"  Body: {r.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

except ImportError:
    print("Install requests: pip install requests")
except Exception as e:
    print(f"API test error: {e}")

print("\nDone.")
