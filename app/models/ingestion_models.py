"""
Database models for email/SMS ingestion.
Indexes: ProcessedEmail.gmail_message_id (unique+index), IngestedTransaction.user_id, created_at.
UploadedSMS/ProcessedSMS for SMS ingestion.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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
