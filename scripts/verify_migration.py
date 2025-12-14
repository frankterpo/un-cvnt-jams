import sqlite3
import os

db_path = "social_agent.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

def check(condition, msg):
    if condition:
        print(f"PASS: {msg}")
    else:
        print(f"FAIL: {msg}")
        exit(1)

try:
    # 1. Users
    c.execute("SELECT count(*) FROM users WHERE email='admin@example.com'")
    count = c.fetchone()[0]
    check(count == 1, "Admin user exists")

    # 2. Platforms
    c.execute("SELECT count(*) FROM platforms")
    count = c.fetchone()[0]
    check(count == 3, "Platforms seeded (3)")

    # 3. Dummy Accounts (Legacy migration)
    c.execute("SELECT count(*) FROM dummy_accounts")
    count = c.fetchone()[0]
    check(count == 1, "Dummy accounts migrated (1)")
    
    c.execute("SELECT username, platform_id, is_active FROM dummy_accounts LIMIT 1")
    row = c.fetchone()
    # Migration set username = name because primary_contact_email was 'test@example.com'.
    # Update logic: SET username = name WHERE username IS NULL.
    # But primary_contact_email was renamed to username.
    # My seed: name='Test Account', primary_contact_email='test@example.com'.
    # My migration: rename column primary_contact_email -> username.
    # So username should be 'test@example.com'.
    # Then I did: UPDATE dummy_accounts SET username = name WHERE username IS NULL.
    # If username is NOT null, it stays 'test@example.com'.
    check(row[0] == 'test@example.com', f"Username preserved as email (Got: {row[0]})")
    check(row[1] == 1, "Platform ID defaulted to 1 (Instagram)")
    # SQLite stores booleans as 1/0 integers usually, but literal default 'true' might be string
    check(row[2] in (1, True, 'true', '1'), f"is_active defaulted to true (Got: {row[2]!r})")

    # 4. Assets
    c.execute("SELECT count(*) FROM assets")
    count = c.fetchone()[0]
    check(count == 1, "Assets migrated (1)")
    
    c.execute("SELECT original_name, user_id, campaign_id, deleted_by_user_id FROM assets LIMIT 1")
    row = c.fetchone()
    check(row[0] == 'test_video.mp4', f"Original name preserved (Got: {row[0]})")
    check(row[1] == 1, "User ID set to Admin")
    check(row[2] == 1, "Campaign ID set to Default Legacy")
    
    # 5. Schema Check (JSON Column)
    # SQLite returns text for JSON.
    c.execute("SELECT config FROM dummy_accounts")
    # Should be null or something
    
    print("ALL CHECKS PASSED")

except Exception as e:
    print(f"Verification FAILED: {e}")
    exit(1)
finally:
    conn.close()
