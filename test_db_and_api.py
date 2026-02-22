"""
Run from project root: python test_db_and_api.py
Tests (1) transactions table structure and sample data via Flask-SQLAlchemy, (2) dashboard API endpoints.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

# --- 1) Database: transactions table via SQLAlchemy ---
print("=== Database: TRANSACTIONS TABLE ===")
try:
    from app import create_app
    from app.models.ingestion_models import db
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        # PostgreSQL: information_schema; MySQL has different schema
        try:
            r = db.session.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'transactions'
                ORDER BY ordinal_position
            """))
            rows = r.fetchall()
        except Exception:
            rows = []
        if rows:
            print("Structure:")
            for row in rows:
                print(f"  {row[0]}: {row[1]}")
        else:
            print("  (table or schema not found; may be MySQL or empty)")

        print("\nSample data (LIMIT 3):")
        r = db.session.execute(text("SELECT * FROM transactions LIMIT 3"))
        rows = r.mappings().fetchall()
        for row in rows:
            print(f"  {dict(row)}")
        if not rows:
            print("  (no rows)")
except Exception as e:
    print(f"Database Error: {e}")
    sys.exit(1)

# --- 2) Dashboard API (app must be running on 127.0.0.1:5000) ---
print("\n=== Dashboard API (requires server running) ===")
try:
    import requests
    import json

    base_url = "http://127.0.0.1:5000"

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
