# Synthetic Transaction Data Generator

## How to run

From the **project root** (`Expenso_final`):

```bash
# Generate for all users (reads user IDs from `users` table)
python scripts/generate_synthetic_data.py

# Clear previous synthetic data, then generate for all users
python scripts/generate_synthetic_data.py --clear

# Generate only for specific user IDs
python scripts/generate_synthetic_data.py --user-ids 1 2 3

# Clear + generate for users 1 and 2, 400–600 txns per user, last 120 days
python scripts/generate_synthetic_data.py --clear --user-ids 1 2 --min-txns 400 --max-txns 600 --days 120
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--clear` | Delete existing synthetic rows (`raw_text` like `SYNTHETIC:%`) before generating | off |
| `--user-ids 1 2 3` | Only these user IDs | all users from DB |
| `--days N` | Spread transactions over last N days | 180 |
| `--min-txns N` | Min transactions per user | 300 |
| `--max-txns N` | Max transactions per user | 800 |
| `--batch-size N` | Bulk insert batch size | 500 |

## Example output logs

```
[generate_synthetic_data] Found 2 user(s): [1, 2]
[generate_synthetic_data] Cleared previous synthetic data: 1247 row(s) deleted.
[generate_synthetic_data] user_id=1 inserted=542 (total so far=542)
[generate_synthetic_data] user_id=2 inserted=618 (total so far=1160)
[generate_synthetic_data] Done. Total transactions inserted: 1160
```

Without `--clear` and with explicit user IDs:

```
[generate_synthetic_data] Using user IDs: [1, 2]
[generate_synthetic_data] user_id=1 inserted=412 (total so far=412)
[generate_synthetic_data] user_id=2 inserted=589 (total so far=1001)
[generate_synthetic_data] Done. Total transactions inserted: 1001
```

If no users exist:

```
[generate_synthetic_data] No users found. Use --user-ids 1 2 3 or create users first.
```

## Data rules

- **Salary**: `transaction_type=credited`, amount 20,000–80,000.
- **Food / Travel / Shopping / Entertainment / Bills / Transfer**: `transaction_type=debited`, with the amount ranges from the script.
- **Merchants**: Swiggy, Zomato, Amazon, Flipkart, Uber, Ola, Netflix, Spotify, SBI, HDFC, ICICI, UPI transfers.
- **Source**: Random `email` or `sms`.
- **raw_text**: Synthetic SMS-style text; all synthetic rows start with `SYNTHETIC:` so `--clear` can remove only them.
