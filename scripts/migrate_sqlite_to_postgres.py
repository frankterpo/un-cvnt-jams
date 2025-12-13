#!/usr/bin/env python3
"""Migrate entire database from SQLite to PostgreSQL."""

import sys
import argparse
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.db.base import Base
from agent.db.models import Account, UploadedAsset, PublishingRunPost, PublishingRunPostContent

# Order matters for foreign keys!
MODELS_ORDERED = [
    Account,
    UploadedAsset,
    PublishingRunPost,
    PublishingRunPostContent
]

def migrate(source_url: str, target_url: str):
    print(f"Migrating from {source_url} -> {target_url}")
    
    # 1. Setup Source
    source_engine = create_engine(source_url)
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()
    
    # 2. Setup Target
    # Ensure target params are production ready if needed, or simple for migration
    target_engine = create_engine(target_url, echo=False)
    TargetSession = sessionmaker(bind=target_engine)
    target_session = TargetSession()

    try:
        # 3. Create Schema on Target (if not exists)
        # Using Alembic is better, but Base.metadata.create_all is a quick fallback/check
        print("Ensuring target schema exists...")
        Base.metadata.create_all(target_engine)

        # 4. Migrate Data
        for ModelClass in MODELS_ORDERED:
            table_name = ModelClass.__table__.name
            print(f"Migrating table: {table_name}...")
            
            # Fetch all from source
            records = source_session.query(ModelClass).all()
            print(f"   Functions found: {len(records)} records.")
            
            if not records:
                continue
                
            # Bulk insert into target
            # We use core insert to allow explicit ID insertion easily if needed,
            # but ORM add_all works if we detach instances.
            
            # Method: Expunge from source, add to target.
            # Must remove _sa_instance_state
            
            new_records = []
            for r in records:
                source_session.expunge(r) # detach
                # Create a clear copy to avoid session conflicts
                data = {c.name: getattr(r, c.name) for c in ModelClass.__table__.columns}
                new_records.append(data)

            if new_records:
                # Use Core Insert for speed and simplicity with IDs
                target_session.execute(
                    ModelClass.__table__.insert(),
                    new_records
                )
                print(f"   Inserted {len(new_records)} records.")

                # Reset Sequence for Postgres (Auto Increment fix)
                # Assuming standard 'tablename_id_seq' naming convention
                if target_engine.dialect.name == 'postgresql':
                    seq_name = f"{table_name}_id_seq"
                    # Check if max id exists
                    max_id = target_session.execute(text(f"SELECT MAX(id) FROM {table_name}")).scalar()
                    if max_id:
                        print(f"   Resetting sequence {seq_name} to {max_id + 1}")
                        target_session.execute(text(f"SELECT setval('{seq_name}', {max_id})"))

        target_session.commit()
        print("\nMigration Successful!")

    except Exception as e:
        print(f"\nMIGRATION FAILED: {e}")
        target_session.rollback()
        import traceback
        traceback.print_exc()
    finally:
        source_session.close()
        target_session.close()

def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to Postgres")
    parser.add_argument("--source", default="sqlite:///social_agent.db", help="Source DB URL")
    parser.add_argument("--target", required=True, help="Target DB URL")
    
    args = parser.parse_args()
    
    if "sqlite" not in args.source:
        print("Warning: Source isn't sqlite? Proceeding anyway.")
        
    migrate(args.source, args.target)

if __name__ == "__main__":
    main()
