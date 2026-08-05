import os
import sys
if sys.platform == 'win32':
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-10) # Get standard input handle
    
    mode = ctypes.c_uint32()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    
    # 0x0040 is QuickEdit Mode. We use bitwise NOT (~) to turn ONLY this off.
    # 0x0080 is Extended Flags, which must be enabled to change QuickEdit.
    mode.value = (mode.value & ~0x0040) | 0x0080
    
    kernel32.SetConsoleMode(handle, mode.value)




import time
import uuid
import queue
import sqlite3
import threading
from typing import Optional
from datetime import datetime
from paths.path import DB_FILE
from model.session import Session
from model.sessions_tatus import SessionStatus
from model.detection_event import DetectionEvent
from database.database import initialize_database
from model.activity_snapshot import ActivitySnapshot
from monitor.monitors import CombinedActivityMonitor




# Global Variables

event_bus = queue.Queue()



class SessionManager:
    def __init__(self):
        self.current_session: Optional[Session] = None

    def start_session(self, planned_duration_sec: int, inactivity_threshold_sec: int) -> Session:
        self.current_session = Session(
            session_id=str(uuid.uuid4()),
            planned_duration_seconds=planned_duration_sec,
            inactivity_threshold_seconds=inactivity_threshold_sec,
            start_time=datetime.now(),
            status=SessionStatus.ACTIVE
        )
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (session_id, start_time, status, planned_duration_seconds, inactivity_threshold_seconds)
                VALUES (?, ?, ?, ?, ?)
            """, (
                self.current_session.session_id, 
                self.current_session.start_time.strftime("%Y-%m-%dT%H:%M:%S"), 
                self.current_session.status.value,
                self.current_session.planned_duration_seconds,
                self.current_session.inactivity_threshold_seconds
            ))
            conn.commit()
            
        print(f"\n[SESSION] Started Tracking. Session ID: {self.current_session.session_id}")
        return self.current_session

    def end_session(self, reason: str) -> Optional[Session]:
        if not self.current_session or self.current_session.status != SessionStatus.ACTIVE:
            return None
            
        self.current_session.end_time = datetime.now()
        self.current_session.status = SessionStatus.COMPLETED
        self.current_session.termination_reason = reason
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions SET end_time = ?, status = ?, termination_reason = ? WHERE session_id = ?
            """, (
                self.current_session.end_time.strftime("%Y-%m-%dT%H:%M:%S"), 
                self.current_session.status.value, 
                self.current_session.termination_reason,
                self.current_session.session_id
            ))
            conn.commit()
        
        completed = self.current_session
        print(f"\n[SESSION] Ended Session [{reason}]. Total time: {completed.get_duration_seconds():.1f}s")
        self.current_session = None 
        return completed




# THE CONSUMER THREAD
def process_queue_data():
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
            print(f">>> [DATABASE] Saved EVENT: {data_item.event_type}")
            
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
            
        conn.commit()
        event_bus.task_done()




def final_data_flush(monitor):
    final_data = monitor.get_snapshot()
    event_bus.put(final_data)




def main():
    # print("Files found:", os.path.exists("reminder.wav"), os.path.exists("aggressive.wav"))
    print("=== FocusGuard Configuration ===")
    
    # Fetching teh user inputs
    try:
        session_mins = float(input("Enter planned study duration (in minutes): "))
        alarm_mins = float(input("Enter inactivity time before alert triggers (in minutes): "))
    except ValueError:
        print("Invalid input. Defaulting to 5 minute session and 0.5 minute (12 sec) alarm.")
        session_mins = 5.0
        alarm_mins = 0.5
    
    try:
        user_dist = float(input("Enter mouse distance to stop alarm (min 500px): "))
        base_distance = max(500.0, user_dist)
    except ValueError:
        base_distance = 500.0

    try:
        user_clicks = int(input("Enter mouse clicks to stop alarm (min 25): "))
        base_clicks = max(25, user_clicks)
    except ValueError:
        base_clicks = 25
        
    print(f"\n[CONFIG] Wake-up requires: {base_distance}px OR {base_clicks} clicks.")
    
    planned_duration_sec = int(session_mins * 60)
    inactivity_threshold_sec = int(alarm_mins * 60)

    # 2. Initialize DB and Consumer
    initialize_database()
    consumer_thread = threading.Thread(target=process_queue_data, daemon=True)
    consumer_thread.start()

    # 3. Start Session with User Config
    session_manager = SessionManager()
    active_session = session_manager.start_session(
        planned_duration_sec=planned_duration_sec,
        inactivity_threshold_sec=inactivity_threshold_sec
    )

    # 4. Start Hardware Sensors
    monitor = CombinedActivityMonitor(
        session_id=active_session.session_id, 
        inactivity_threshold_seconds=inactivity_threshold_sec,
        base_distance=base_distance,    
        base_clicks=base_clicks,
        event_bus= event_bus
    )
    monitor.start()

    # 5. Main Loop (Checks time dynamically instead of just sleeping)
    print(f"\nMonitoring hardware. Will auto-stop in {planned_duration_sec} seconds.")
    print("Press Ctrl+C to stop manually.")
    
    last_snapshot_time = time.monotonic()
    
    try:
        while True:
            current_time = time.monotonic()
            
            # Auto-Kill Check
            if active_session.get_duration_seconds() >= active_session.planned_duration_seconds:
                print("\n[SYSTEM] Planned study duration reached! Generating summary and shutting down...")
                final_data_flush(monitor= monitor)
                monitor.stop()
                session_manager.end_session(reason="AUTO_COMPLETE")
                break
                
            # Snapshot Generator
            if current_time - last_snapshot_time >= monitor.data_print_time:
                data = monitor.get_snapshot()
                event_bus.put(data)
                last_snapshot_time = current_time
            
            # Sleep slightly to prevent high CPU usage, but keep loop responsive
            time.sleep(0.5) 
            
    except KeyboardInterrupt:
        print(f"\n\n[SYSTEM] Ctrl+C Detected. Shutting down...")
        final_data_flush(monitor= monitor)
        monitor.stop()
        # Mark as MANUAL_STOP in the database
        session_manager.end_session(reason="MANUAL_STOP")

    # Final Save
    print("[SYSTEM] Waiting for remaining data to save to database...")
    event_bus.join()
    print("[SYSTEM] All data successfully saved. Goodbye!")















if __name__ == "__main__":
    main()


