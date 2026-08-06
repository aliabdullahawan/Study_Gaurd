import uuid
import sqlite3
from typing import Optional
from datetime import datetime
from constants.path import DB_FILE
from model.session import Session
from model.sessions_tatus import SessionStatus









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

