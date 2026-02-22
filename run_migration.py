#!/usr/bin/env python3
"""
Database Migration Script for TOTP Support
Run this script to add TOTP columns to your users table.
Uses Flask-SQLAlchemy (SQLALCHEMY_DATABASE_URI). No direct MySQL connection.
"""

import os
import sys

# Project root on path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.models.ingestion_models import db
from sqlalchemy import text


def run_migration():
    """Run the TOTP migration using Flask-SQLAlchemy."""
    app = create_app()
    with app.app_context():
        try:
            print("🔧 Running TOTP database migration...")

            migrations = [
                ("ALTER TABLE users ADD COLUMN totp_secret VARCHAR(32) NULL", "totp_secret"),
                ("CREATE INDEX IF NOT EXISTS idx_users_totp_secret ON users(totp_secret)", "idx_users_totp_secret"),
                ("ALTER TABLE users ADD COLUMN totp_enabled_at TIMESTAMP NULL", "totp_enabled_at"),
                ("UPDATE users SET totp_secret = NULL WHERE totp_secret IS NULL", "update"),
            ]

            for i, (sql, label) in enumerate(migrations, 1):
                try:
                    print(f"  {i}. Running: {sql[:50]}...")
                    db.session.execute(text(sql))
                    db.session.commit()
                    print(f"     ✅ Success")
                except Exception as e:
                    err_str = str(e).lower()
                    if "duplicate column" in err_str or "already exists" in err_str or "duplicate key" in err_str:
                        print(f"     ⚠️  Already exists (skipping)")
                        db.session.rollback()
                    else:
                        print(f"     ❌ Error: {e}")
                        db.session.rollback()
                        raise

            print("\n🎉 TOTP migration completed successfully!")
            print("✅ Your database now supports TOTP authentication")
            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            print("\n🔧 Troubleshooting:")
            print("1. Ensure DATABASE_URL (or MYSQL_*) is set in .env")
            print("2. Ensure the database is running and reachable")
            print("3. Ensure the 'users' table exists")
            return False


if __name__ == "__main__":
    print("🚀 TOTP Database Migration Tool")
    print("=" * 40)

    success = run_migration()

    if success:
        print("\n🚀 Next steps:")
        print("1. Start your Flask server: python start_server.py --https")
        print("2. Access your app at: https://localhost:5000")
        print("3. Test TOTP authentication!")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
