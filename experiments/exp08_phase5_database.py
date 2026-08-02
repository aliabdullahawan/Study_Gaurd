import sys
if sys.platform == 'win32':
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 0x0080)

import time
import threading
import math
import queue
import uuid
import sqlite3
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from pynput import mouse, keyboard

# --- DATABASE CONFIGURATION ---
DB_FILE = "focusguard.db"

def initialize_database():
    """Creates the SQLite database and tables if they do not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Sessions Table (Parent)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL
        )
    """)
    
    # 2. Events Table (Child)
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
    
    # 3. Metrics Table (Child)
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
    print("[DATABASE] Tables initialized successfully.")

# --- DATACLASSES ---
@dataclass
class ActivitySnapshot:
    session_id: str 
    timestamp: str
    is_active: bool
    mouse_distance_pixels: float
    mouse_click_count: int
    mouse_scroll_count: int
    key_press_count: int
    inactivity_seconds: float
    inactivity_triggered: bool

@dataclass
class DetectionEvent:
    session_id: str 
    timestamp: str
    event_type: str
    description: str

# --- THREAD-SAFE QUEUE ---
event_bus = queue.Queue()

# --- SESSION MANAGEMENT ---
class SessionStatus(Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

@dataclass
class Session:
    session_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: SessionStatus = SessionStatus.IDLE

class SessionManager:
    def __init__(self):
        self.current_session: Optional[Session] = None

    def start_session(self) -> Session:
        if self.current_session and self.current_session.status == SessionStatus.ACTIVE:
            return self.current_session
            
        self.current_session = Session(
            session_id=str(uuid.uuid4()),
            start_time=datetime.now(),
            status=SessionStatus.ACTIVE
        )
        
        # Insert the session into the database immediately so Foreign Keys don't fail
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (session_id, start_time, status)
                VALUES (?, ?, ?)
            """, (self.current_session.session_id, self.current_session.start_time.strftime("%Y-%m-%dT%H:%M:%S"), self.current_session.status.value))
            conn.commit()
            
        print(f"\n[SESSION] Started Tracking. ID Saved to DB: {self.current_session.session_id}")
        return self.current_session

    def end_session(self) -> Optional[Session]:
        if not self.current_session or self.current_session.status != SessionStatus.ACTIVE:
            return None
            
        self.current_session.end_time = datetime.now()
        self.current_session.status = SessionStatus.COMPLETED
        
        # Update the end_time and status in the database
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions SET end_time = ?, status = ? WHERE session_id = ?
            """, (self.current_session.end_time.strftime("%Y-%m-%dT%H:%M:%S"), self.current_session.status.value, self.current_session.session_id))
            conn.commit()
        
        completed = self.current_session
        print(f"\n[SESSION] Ended Session ID: {completed.session_id}")
        self.current_session = None 
        return completed

# --- SENSORS (Using your Parent Referencing) ---
class MouseMonitor:
    def __init__(self, parent):
        self.parent = parent
        self.last_x = None
        self.last_y = None
        self.distance_threshold = 100
        self.unpause_threshold = 5
        self.click_count = 0
        self.scroll_count = 0
        self.total_distance = 0
        self.listener = None

    def update_timestamp(self):
        if not self.parent.is_inactive:
            self.parent.last_active_time = time.monotonic()

    def on_move(self, x, y):
        if self.last_x is None and self.last_y is None:
            self.last_x, self.last_y = x, y
            return
        
        distance = math.sqrt((x - self.last_x)**2 + (y - self.last_y)**2)
        self.last_x, self.last_y = x, y
        self.total_distance += distance
        
        if self.parent.is_inactive:
            self.parent.accumulated_distance += distance
            if self.parent.accumulated_distance >= self.distance_threshold:
                self.parent.wake_up(f"Mouse moved {self.parent.accumulated_distance:.1f}px")
        else:
            self.update_timestamp()

    def on_click(self, x, y, button, pressed):
        self.update_timestamp()
        if pressed:
            self.click_count += 1
            if self.parent.is_inactive:
                self.parent.unpause_click_count += 1
                if self.parent.unpause_click_count >= self.parent.unpause_threshold:
                    self.parent.wake_up(f"Mouse clicked {self.parent.unpause_click_count} times")

    def on_scroll(self, x, y, dx, dy):
        self.update_timestamp()
        self.scroll_count += 1
        if self.parent.is_inactive:
            self.parent.unpause_scroll_count += 1
            if self.parent.unpause_scroll_count >= self.parent.unpause_threshold:
                self.parent.wake_up(f"Mouse scrolled {self.parent.unpause_scroll_count} times")

    def start(self):
        self.listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            self.listener.stop()

class KeyboardMonitor:
    def __init__(self, parent):
        self.parent = parent
        self.key_press_count = 0
        self.unpause_key_threshold = 5
        self.listener = None

    def update_timestamp(self):
        if not self.parent.is_inactive:
            self.parent.last_active_time = time.monotonic()

    def on_press(self, key):
        self.update_timestamp()
        self.key_press_count += 1
        
        if self.parent.is_inactive:
            self.parent.unpause_key_count += 1
            if self.parent.unpause_key_count >= self.parent.unpause_key_threshold:
                self.parent.wake_up(f"Typed {self.parent.unpause_key_threshold} keys")

    def start(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            self.listener.stop()

# --- COMBINED MONITOR ---
class CombinedActivityMonitor:
    def __init__(self, session_id: str):
        self.session_id = session_id
        
        self.mouse = MouseMonitor(self)
        self.keyboard = KeyboardMonitor(self)
        
        self.inactive_threshold = 5.0
        self.is_inactive = False
        self.activity_thread = None
        self.data_print_time = 5.0

        self.accumulated_distance = 0
        self.unpause_click_count = 0
        self.unpause_scroll_count = 0
        self.unpause_key_count = 0
        
        self.last_active_time = time.monotonic()

    def get_latest_activity_time(self):
        return self.last_active_time

    def wake_up(self, reason):
        self.is_inactive = False
        self.accumulated_distance = 0
        self.unpause_click_count = 0
        self.unpause_scroll_count = 0
        self.unpause_key_count = 0
        self.last_active_time = time.monotonic()
        
        resume_event = DetectionEvent(
            session_id=self.session_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            event_type="ACTIVITY_RESUMED",
            description=reason
        )
        event_bus.put(resume_event)

    def monitor_inactivity(self):
        while True:
            current_time = time.monotonic() - self.get_latest_activity_time()
            if current_time >= self.inactive_threshold and not self.is_inactive:
                self.is_inactive = True
                
                alert_event = DetectionEvent(
                    session_id=self.session_id,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    event_type="INACTIVITY_ALERT",
                    description=f"User inactive for {self.inactive_threshold} seconds."
                )
                event_bus.put(alert_event)
            time.sleep(0.5)

    def start(self):
        self.activity_thread = threading.Thread(target=self.monitor_inactivity, daemon=True)
        self.activity_thread.start()
        self.mouse.start()
        self.keyboard.start()

    def stop(self):
        self.mouse.stop()
        self.keyboard.stop()

    def get_snapshot(self):
        inactivity_seconds = time.monotonic() - self.get_latest_activity_time()
        
        snapshot = ActivitySnapshot(
            session_id=self.session_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            is_active=not self.is_inactive,
            mouse_distance_pixels=round(self.mouse.total_distance, 2),
            mouse_click_count=self.mouse.click_count,
            mouse_scroll_count=self.mouse.scroll_count,
            key_press_count=self.keyboard.key_press_count,
            inactivity_seconds=max(0.0, round(inactivity_seconds, 2)),
            inactivity_triggered=self.is_inactive
        )
        
        self.mouse.total_distance = 0.0
        self.mouse.click_count = 0
        self.mouse.scroll_count = 0
        self.keyboard.key_press_count = 0
        
        return snapshot

# --- THE CONSUMER THREAD (Database Writer) ---
def process_queue_data():
    print("[CONSUMER] Database processor thread started. Connecting to SQLite...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    while True:
        data_item = event_bus.get() 
        
        if isinstance(data_item, DetectionEvent):
            cursor.execute("""
                INSERT INTO events (session_id, timestamp, event_type, description)
                VALUES (?, ?, ?, ?)
            """, (data_item.session_id, data_item.timestamp, data_item.event_type, data_item.description))
            print(f"\n>>> [DATABASE] Saved EVENT: {data_item.event_type}")
            
        elif isinstance(data_item, ActivitySnapshot):
            cursor.execute("""
                INSERT INTO metrics (
                    session_id, timestamp, is_active, mouse_distance_pixels, 
                    mouse_click_count, mouse_scroll_count, key_press_count, 
                    inactivity_seconds, inactivity_triggered
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_item.session_id, data_item.timestamp, data_item.is_active, 
                data_item.mouse_distance_pixels, data_item.mouse_click_count, 
                data_item.mouse_scroll_count, data_item.key_press_count, 
                data_item.inactivity_seconds, data_item.inactivity_triggered
            ))
            print(f"\n>>> [DATABASE] Saved SNAPSHOT. Inactive Secs: {data_item.inactivity_seconds}")
            
        conn.commit()
        event_bus.task_done()

# --- MAIN EXECUTION ---
def main():
    # 1. Initialize the SQLite Tables
    initialize_database()

    # 2. Start the Queue Consumer
    consumer_thread = threading.Thread(target=process_queue_data, daemon=True)
    consumer_thread.start()

    # 3. Start a New Session
    session_manager = SessionManager()
    active_session = session_manager.start_session()

    # 4. Start the Sensors
    monitor = CombinedActivityMonitor(session_id=active_session.session_id)
    print("Monitoring hardware activity. Press Ctrl+C to safely exit and save.")
    monitor.start()

    # 5. Main Loop (Producer)
    try:
        while True:
            time.sleep(monitor.data_print_time)
            data = monitor.get_snapshot()
            event_bus.put(data)
            
    except KeyboardInterrupt:
        print(f"\n\n[SYSTEM] Ctrl+C Detected. Shutting down...")
        
        # Stop tracking
        monitor.stop()
        
        # End the session formally and update the database
        session_manager.end_session()
        
        # Wait for the queue to finish writing the final snapshots
        print("[SYSTEM] Waiting for remaining data to save to database...")
        event_bus.join()
        print("[SYSTEM] All data successfully saved. Goodbye!")

if __name__ == "__main__":
    main()