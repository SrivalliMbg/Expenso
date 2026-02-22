# Ingestion constants. Shared by email and SMS.

# Safe max length for raw_text in DB; prevents huge payloads.
RAW_TEXT_MAX_LENGTH = 4096

# Max email body size to decode (chars). Larger bodies are truncated before parsing/storage.
BODY_TEXT_MAX_LENGTH = 100_000

# Hard cap for Gmail API and pipeline.
MAX_EMAILS_PER_RUN = 100

# SMS: max body length when storing UploadedSMS; also used when returning text to pipeline.
SMS_BODY_MAX_LENGTH = 4096

# SMS ingestion: cap for max_messages per run.
MAX_SMS_PER_RUN = 200
