

import sqlite3
from constants.path import DB_FILE



def initialize_database():
    """Creates the SQLite database with the NEW user configuration columns."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Sessions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL,
            planned_duration_seconds INTEGER,
            inactivity_threshold_seconds INTEGER,
            termination_reason TEXT
        )
    """)
    
    # 2. Events Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        )
    """)
    
    # 3. Metrics Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_active BOOLEAN NOT NULL,
            mouse_distance_pixels REAL,
            mouse_click_count INTEGER,
            mouse_scroll_count INTEGER,
            key_press_count INTEGER,
            inactivity_seconds REAL,
            inactivity_triggered BOOLEAN,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

