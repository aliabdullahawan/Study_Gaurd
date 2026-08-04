


from enum import Enum
from typing import Optional
from datetime import datetime
from dataclasses import dataclass







class SessionStatus(Enum):
    MANUAL_STOP = "IDLE"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"



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



@dataclass
class Session:
    session_id: str
    planned_duration_seconds: int
    inactivity_threshold_seconds: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: SessionStatus = SessionStatus.IDLE
    termination_reason: str = None
    
    def get_duration_seconds(self) -> float:
        if self.start_time is None: return 0.0
        end = self.end_time if self.end_time else datetime.now()
        return (end - self.start_time).total_seconds()


