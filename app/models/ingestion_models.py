"""
Database models for email/SMS ingestion and core app (User).
Indexes: ProcessedEmail.gmail_message_id (unique+index), IngestedTransaction.user_id, created_at.
UploadedSMS/ProcessedSMS for SMS ingestion.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """Core user table (login, profile, TOTP). Used by routes via raw SQL; model ensures table is created by create_all()."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(64), nullable=True, default="professional")
    dob = db.Column(db.Date, nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    profession = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    totp_secret = db.Column(db.String(64), nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=True)
    totp_enabled_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<User {self.username}>"


class ResetOTP(db.Model):
    """OTP records for forgot-password flow. Rate-limit and expiry are enforced in app logic."""
    __tablename__ = "reset_otps"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    identifier = db.Column(db.String(255), nullable=False, index=True)
    otp = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    reset_token = db.Column(db.String(64), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ResetOTP id={self.id} identifier={self.identifier}>"


class ProcessedEmail(db.Model):
    """Tracks which Gmail messages have already been processed (dedup)."""
    __tablename__ = "processed_emails"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    gmail_message_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ProcessedEmail {self.gmail_message_id}>"


class IngestedTransaction(db.Model):
    """Extracted transaction from email or SMS (source-agnostic)."""
    __tablename__ = "ingested_transactions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    transaction_type = db.Column(db.String(32), nullable=True)
    source = db.Column(db.String(16), nullable=False, default="email")
    raw_text = db.Column(db.Text, nullable=True)
    extracted_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<IngestedTransaction {self.id} {self.amount} {self.source}>"


class UserIngestionState(db.Model):
    """Per-user ingestion state: last_ingested_at to avoid reprocessing old ranges."""
    __tablename__ = "user_ingestion_state"

    user_id = db.Column(db.Integer, primary_key=True)
    last_ingested_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UploadedSMS(db.Model):
    """SMS messages uploaded from client (e.g. Android). Persisted for later ingestion; no parsing on upload."""
    __tablename__ = "uploaded_sms"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    device_sms_id = db.Column(db.String(128), nullable=False, index=True)
    body = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "device_sms_id", name="uq_uploaded_sms_user_device"),)


class ProcessedSMS(db.Model):
    """Tracks which uploaded SMS have been processed (dedup for SMS ingestion)."""
    __tablename__ = "processed_sms"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    device_sms_id = db.Column(db.String(128), nullable=False, index=True)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "device_sms_id", name="uq_processed_sms_user_device"),)
