-- Ingestion tables (email/SMS). Optional: run if not using Flask-SQLAlchemy create_all.

CREATE TABLE IF NOT EXISTS processed_emails (
    id INT AUTO_INCREMENT PRIMARY KEY,
    gmail_message_id VARCHAR(64) NOT NULL,
    user_id INT NOT NULL,
    processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_gmail_message_id (gmail_message_id),
    INDEX idx_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS ingested_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    transaction_type VARCHAR(32) NULL,
    source VARCHAR(16) NOT NULL DEFAULT 'email',
    raw_text TEXT NULL,
    extracted_date DATE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);
