import sqlite3
from constants.path import DB_FILE

def initialize_database():
    """Creates the SQLite database with the NEW user configuration and AI columns."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Sessions Table (UNCHANGED)
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
    
    # 2. Events Table (UNCHANGED - This will hold both Inactivity AND Vision Alarms)
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
    
    # 3. Metrics Table (UPDATED - Now holds Hardware + Vision AI data!)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            
            -- Hardware Tracking
            is_active BOOLEAN NOT NULL,
            mouse_distance_pixels REAL,
            mouse_click_count INTEGER,
            mouse_scroll_count INTEGER,
            key_press_count INTEGER,
            inactivity_seconds REAL,
            inactivity_triggered BOOLEAN,
            
            -- Vision Tracking (New)
            ear REAL,
            mar REAL,
            pitch REAL,
            yaw REAL,
            roll REAL,
            
            -- Fatigue Tracking (New)
            total_blinks INTEGER,
            total_yawns INTEGER,
            total_posture_warnings INTEGER,
            fatigue_score INTEGER,
            fatigue_state TEXT,
            
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        )
    """)

    # 4. Calibration Settings Table (NEW - So you don't have to calibrate every time)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_calibration (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            ear_threshold REAL,
            mar_threshold REAL,
            base_pitch REAL,
            base_yaw REAL,
            base_roll REAL,
            pitch_limit REAL,
            yaw_limit REAL,
            roll_limit REAL,
            
            -- User Preferences (New)
            eye_closure_threshold_sec REAL,
            inactivity_threshold_sec REAL,
            mouse_distance_threshold REAL,
            mouse_click_threshold INTEGER,
            alarm_cooldown_sec REAL,
            last_updated TEXT
        )
    """)
    
    conn.commit()
    conn.close()