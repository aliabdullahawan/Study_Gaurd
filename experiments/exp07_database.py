import sqlite3
import uuid
from datetime import datetime

# Define the database file name
DB_FILE = "focusguard_test.db"

def initialize_database():
    """Creates the database file and builds the tables if they don't exist."""
    
    # 1. Open a connection 
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 2. SQLite requires Foreign Keys to be manually turned on per connection
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 3. Create the Parent Table (Sessions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL
        )
    """)
    
    # 4. Create the Child Table (Metrics)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_active BOOLEAN NOT NULL,
            mouse_distance_pixels REAL,
            key_press_count INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        )
    """)
    
    
    conn.commit()
    print("[DATABASE] Tables initialized successfully.")
    return conn

def simulate_data_insertion(conn):
    """Simulates saving the dataclasses we built in Phase 4."""
    cursor = conn.cursor()
    
    test_session_id = str(uuid.uuid4())
    current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    cursor.execute("""
        INSERT INTO sessions (session_id, start_time, status)
        VALUES (?, ?, ?)
    """, (test_session_id, current_time, "ACTIVE"))
    
    print(f"[DATABASE] Inserted Session: {test_session_id}")
    
    cursor.execute("""
        INSERT INTO metrics (session_id, timestamp, is_active, mouse_distance_pixels, key_press_count)
        VALUES (?, ?, ?, ?, ?)
    """, (test_session_id, current_time, True, 450.5, 12))
    
    print(f"[DATABASE] Inserted 5-Second Metric Snapshot linked to session.")
    
    conn.commit()
    
    print("\n--- DATABASE VERIFICATION ---")
    cursor.execute("SELECT * FROM metrics WHERE session_id = ?", (test_session_id,))
    rows = cursor.fetchall()
    for row in rows:
        print(f"Row pulled from SQLite: {row}")

if __name__ == "__main__":
    connection = initialize_database()
    simulate_data_insertion(connection)
    connection.close()