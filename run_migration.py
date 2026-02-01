#!/usr/bin/env python3
"""
Database Migration Script for TOTP Support
Run this script to add TOTP columns to your users table
"""

import mysql.connector
from config import Config

# Create MYSQL_CONFIG from Config class
MYSQL_CONFIG = {
    'host': Config.MYSQL_HOST,
    'user': Config.MYSQL_USER,
    'password': Config.MYSQL_PASSWORD,
    'database': Config.MYSQL_DB
}

def run_migration():
    """Run the TOTP migration"""
    try:
        # Connect to MySQL database
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = connection.cursor()
        
        print("🔧 Running TOTP database migration...")
        
        # Migration SQL commands
        migrations = [
            "ALTER TABLE users ADD COLUMN totp_secret VARCHAR(32) NULL",
            "CREATE INDEX idx_users_totp_secret ON users(totp_secret)",
            "ALTER TABLE users ADD COLUMN totp_enabled_at TIMESTAMP NULL",
            "UPDATE users SET totp_secret = NULL WHERE totp_secret IS NULL"
        ]
        
        for i, migration in enumerate(migrations, 1):
            try:
                print(f"  {i}. Running: {migration[:50]}...")
                cursor.execute(migration)
                print(f"     ✅ Success")
            except mysql.connector.Error as e:
                if "Duplicate column name" in str(e) or "Duplicate key name" in str(e):
                    print(f"     ⚠️  Already exists (skipping)")
                else:
                    print(f"     ❌ Error: {e}")
                    raise
        
        # Commit changes
        connection.commit()
        print("\n🎉 TOTP migration completed successfully!")
        print("✅ Your database now supports TOTP authentication")
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure MySQL is running")
        print("2. Check your database connection in config.py")
        print("3. Ensure the 'users' table exists")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
    
    return True

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

