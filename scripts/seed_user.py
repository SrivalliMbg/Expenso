"""
CLI to ensure a user has synthetic transaction data.
Run from project root: python scripts/seed_user.py --user-id <user_id>
Example: python scripts/seed_user.py --user-id 2
"""
import argparse
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app import create_app
from app.utils.seed_user import ensure_user_has_synthetic_data


def main():
    parser = argparse.ArgumentParser(description="Ensure a user has synthetic transaction data")
    parser.add_argument("--user-id", type=int, required=True, help="User ID to seed")
    args = parser.parse_args()

    if args.user_id < 1:
        print("[seed_user] user_id must be >= 1", file=sys.stderr)
        sys.exit(1)

    app = create_app()
    with app.app_context():
        action, count = ensure_user_has_synthetic_data(args.user_id)
        if action == "already_has_data":
            print(f"[seed_user] User {args.user_id} already has transactions. No action taken.")
        elif action == "copied":
            print(f"[seed_user] Synthetic data copied for user_id={args.user_id} (count={count})")
        else:
            print(f"[seed_user] Synthetic data generated for user_id={args.user_id} (count={count})")


if __name__ == "__main__":
    main()
