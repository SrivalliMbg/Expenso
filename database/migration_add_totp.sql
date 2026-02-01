-- Migration to add TOTP support to users table
-- Run this SQL script to add TOTP functionality to your existing database

-- Add totp_secret column to users table
ALTER TABLE users ADD COLUMN totp_secret VARCHAR(32) NULL;

-- Add index for better performance when checking TOTP status
CREATE INDEX idx_users_totp_secret ON users(totp_secret);

-- Optional: Add a column to track when TOTP was enabled
ALTER TABLE users ADD COLUMN totp_enabled_at TIMESTAMP NULL;

-- Update existing users to have NULL totp_secret (TOTP disabled by default)
UPDATE users SET totp_secret = NULL WHERE totp_secret IS NULL;
