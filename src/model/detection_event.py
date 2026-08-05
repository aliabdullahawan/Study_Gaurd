from dataclasses import dataclass


@dataclass
class DetectionEvent:
    session_id: str 
    timestamp: str
    event_type: str
    description: str