import os
import urllib.parse
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Parse manual params to avoid URL parsing issues
DB_HOST = "social-agent-db.cej60cw482tv.us-east-1.rds.amazonaws.com"
DB_PORT = 5432
DB_NAME = "social_agent"
DB_USER = "socialagent_admin"
DB_PASS = "Sup3rS4feP4ssw0rd!2024" # Retrieved from viewing .env earlier

print(f"Connecting to {DB_HOST} as {DB_USER}...")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        sslmode='require'
    )
    print("SUCCESS: Connection established!")
    conn.close()
except Exception as e:
    print(f"FAILURE: {e}")
