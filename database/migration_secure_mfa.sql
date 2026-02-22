-- Migration: Secure MFA and communication (Step 1)
-- Add columns for email/phone verification, TOTP, and 2FA.
-- If a column already exists (e.g. phone, totp_secret from earlier migrations), skip that line or run the block that follows.

-- Add columns (run each ALTER separately if you get "duplicate column" errors):
ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL;
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN phone_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64) NULL;
ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT FALSE;

-- If totp_secret or phone already exist from previous migrations, run only the new ones:
-- ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
-- ALTER TABLE users ADD COLUMN phone_verified BOOLEAN DEFAULT FALSE;
-- ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT FALSE;

-- OTP stored hashed (SHA-256 hex = 64 chars). Run after reset_otps exists:
-- ALTER TABLE reset_otps MODIFY otp VARCHAR(64) NOT NULL;

-- Table for TOTP verification after login (no session until TOTP verified):
CREATE TABLE IF NOT EXISTS pending_totp_verification (
    token VARCHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_expires (expires_at)
);

-- Temporary TOTP secret during setup (never sent to client; used only in verify step):
CREATE TABLE IF NOT EXISTS totp_setup_pending (
    user_id INT PRIMARY KEY,
    secret VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
