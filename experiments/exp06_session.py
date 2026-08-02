import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import time

# Define the allowed states
class SessionStatus(Enum):
    """Restricts the status to only these three specific states."""
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

# Define a session
@dataclass
class Session:
    session_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: SessionStatus = SessionStatus.IDLE
    
    def get_duration_seconds(self) -> float:
        if self.start_time is None:
            return 0.0
        
        # If the session is still active, calculate the duration up to this exact moment
        end = self.end_time if self.end_time else datetime.now()
        duration = end - self.start_time
        return duration.total_seconds()

# Session manager interface 
class SessionManager:
    def __init__(self):
        self.current_session: Optional[Session] = None

    def start_session(self) -> Session:
        """Creates a new session, assigns a UUID, and sets status to ACTIVE."""
        
        # Prevent starting a session if one is already active
        if self.current_session is not None and self.current_session.status == SessionStatus.ACTIVE:
            print("\n[ERROR] Cannot start a new session. An active session already exists.")
            return self.current_session
            
        # Generate a random UUID string
        new_id = str(uuid.uuid4())
        
        self.current_session = Session(
            session_id=new_id,
            start_time=datetime.now(),
            status=SessionStatus.ACTIVE
        )
        print(f"\n[SESSION] Started new session: {self.current_session.session_id}")
        return self.current_session

    def end_session(self) -> Optional[Session]:
        """Marks the session as COMPLETED and calculates the final time."""
        
        # Cannot end a session if none is running
        if self.current_session is None or self.current_session.status != SessionStatus.ACTIVE:
            print("\n[ERROR] No active session to end.")
            return None
            
        self.current_session.end_time = datetime.now()
        self.current_session.status = SessionStatus.COMPLETED
        
        print(f"\n[SESSION] Ended session: {self.current_session.session_id}")
        print(f"[SESSION] Total duration: {self.calculate_duration():.2f} seconds")
        
        # Keep a reference to return it, but clear the current tracker
        completed_session = self.current_session
        self.current_session = None 
        return completed_session

    def get_active_session(self) -> Optional[Session]:
        return self.current_session

    def calculate_duration(self) -> float:
        if self.current_session:
            return self.current_session.get_duration_seconds()
        return 0.0
        
    def recover_interrupted_session(self):
        # Placeholder for Phase 5 (SQLite Data Layer)
        print("\n[SESSION] Checking database for interrupted sessions... None found.")


def main():
    manager = SessionManager()
    
    manager.start_session()
    
    # Try to start another session while one is already running
    manager.start_session()
    
    print("\nSimulating study activity for 2 seconds...")
    time.sleep(2)
    
    active = manager.get_active_session()
    if active:
        print(f"Current duration: {manager.calculate_duration():.2f} seconds")
        
    # 5. End the session
    manager.end_session()
    
    # Try to end a session that doesn't exist anymore
    manager.end_session()

if __name__ == "__main__":
    main()