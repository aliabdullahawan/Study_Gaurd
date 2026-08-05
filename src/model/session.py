



from typing import Optional
from datetime import datetime
from dataclasses import dataclass, field
from .sessions_tatus import SessionStatus







@dataclass
class Session:
    session_id: str
    planned_duration_seconds: int
    inactivity_threshold_seconds: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: SessionStatus = field(default_factory=lambda: SessionStatus.MANUAL_STOP)
    termination_reason: str = None
    
    def get_duration_seconds(self) -> float:
        if self.start_time is None: return 0.0
        end = self.end_time if self.end_time else datetime.now()
        return (end - self.start_time).total_seconds()


