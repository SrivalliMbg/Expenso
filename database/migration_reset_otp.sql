-- Forgot credentials: OTP storage and reset tokens
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
);
