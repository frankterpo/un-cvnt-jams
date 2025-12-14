import sqlite3
import os

db_path = "social_agent.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

print("Seeding legacy data...")
try:
    c.execute("INSERT INTO accounts (name, primary_contact_email) VALUES ('Test Account', 'test@example.com')")
    c.execute("INSERT INTO uploaded_assets (account_id, storage_key, original_filename, status) VALUES (1, 's3://test/key.mp4', 'test_video.mp4', 'PENDING_PROCESSING')")
    conn.commit()
    print("Seeded successfully.")
except Exception as e:
    print(f"Error seeding: {e}")
    conn.rollback()
finally:
    conn.close()
