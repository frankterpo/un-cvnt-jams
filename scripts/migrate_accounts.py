#!/usr/bin/env python3
"""Migrate accounts from accounts.json to SQLite."""

import json
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.db.base import SessionLocal, engine
from agent.db.models import Account, Base

def main():
    parser = argparse.ArgumentParser(description="Migrate accounts.json to DB")
    parser.add_argument("--dry-run", action="store_true", help="Do not checking changes")
    args = parser.parse_args()

    json_path = Path("accounts.json")
    if not json_path.exists():
        print("No accounts.json found. Skipping.")
        return

    # Ensure tables exist (safety check)
    Base.metadata.create_all(engine)

    with open(json_path, "r") as f:
        data = json.load(f)

    session = SessionLocal()
    try:
        # data is expected to be a dict e.g. {"account_label": {...}} or list?
        # Based on typical structure: {"my_account": {"tiktok":..., "instagram":...}}
        # Or simple list. Let's assume Dict[str, dict] where key is label.
        
        accounts_to_create = []

        if isinstance(data, dict):
            items = data.items()
            for label, details in items:
                # Check if exists
                existing = session.query(Account).filter(Account.name == label).first()
                if existing:
                    print(f"Account '{label}' already exists. Skipping.")
                    continue

                # Try to find an email
                email = None
                # Heuristic: verify if there is an email field or use username from a platform
                if "email" in details:
                    email = details["email"]
                
                print(f"Preparing account: {label} (email: {email})")
                accounts_to_create.append(Account(name=label, primary_contact_email=email))
        
        elif isinstance(data, list):
             for entry in data:
                label = entry.get("label", entry.get("name", "Unknown"))
                existing = session.query(Account).filter(Account.name == label).first()
                if existing:
                    print(f"Account '{label}' already exists. Skipping.")
                    continue
                accounts_to_create.append(Account(name=label))

        if not accounts_to_create:
            print("No new accounts to migrate.")
            return

        if args.dry_run:
            print(f"[DRY RUN] Would create {len(accounts_to_create)} accounts.")
        else:
            session.add_all(accounts_to_create)
            session.commit()
            print(f"Successfully migrated {len(accounts_to_create)} accounts.")

    except Exception as e:
        print(f"Error migrating accounts: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()
