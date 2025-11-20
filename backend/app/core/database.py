from pymongo import MongoClient
import sqlite3
import os
from app.core.config import settings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, settings.SQLITE_DB_PATH)

### connection to the database
client = MongoClient(settings.MONGODB_URL)
conn = client[settings.MONGODB_DATABASE]
collection = conn["records"]

#new sqlite local database setup
try:
    # Connect to the SQLite database (it will be created if it doesn't exist)
    sqlite_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    sqlite_cursor = sqlite_conn.cursor()
    # Create the patient table if it doesn't exist
    sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            phone TEXT UNIQUE NOT NULL,
            registration_date TEXT,
            billed_amount REAL,
            outstanding_amount REAL
        )
    """)
    sqlite_conn.commit()
except Exception as e:
    print(f"Error setting up SQLite database: {e}")

