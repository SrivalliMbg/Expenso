# Email (and future SMS) Ingestion

## Architecture

- **Gmail service** (`gmail_service.py`): OAuth2 via stored tokens; fetches messages with Gmail search query and optional `after:YYYY/MM/DD`. Does not read entire inbox.
- **Parser** (`parser.py`): Keyword threshold (`is_relevant`) + regex extraction (amount, transaction_type, date). Shared so SMS can use the same logic.
- **Pipeline** (`ingestion_pipeline.py`): Fetch → skip processed → keyword filter → extract → store `IngestedTransaction` → mark `ProcessedEmail`.
- **Models** (`app/models/ingestion_models.py`): `ProcessedEmail` (dedup), `IngestedTransaction` (source=email|sms).

## Adding SMS later

1. Add an SMS fetcher (e.g. Twilio or web API) that returns list of `{ "id", "body_text" }`.
2. In a new function (e.g. `run_sms_ingestion_pipeline`), for each message: skip if external_id already in a new `ProcessedSms` (or reuse a generic `processed_messages` with source column), then call `is_relevant(body_text)` and `extract_transaction_data(body_text)` from `parser.py`, then store `IngestedTransaction(source="sms", ...)`.
3. Reuse the same keyword list and regex in `parser.py`; no changes needed there.

## Security

- Gmail: `gmail.readonly` only; tokens from DB (encrypted); no plain passwords.
- All secrets from environment (see `config.py`).

## Manual trigger

- `POST /api/ingestion/run` (body optional: `after_date`, `max_emails`, `query`).
- `GET /api/ingestion/transactions` (paginated list of ingested transactions).
