from enum import Enum
from dataclasses import dataclass


@dataclass
class SessionStatus(Enum):
    MANUAL_STOP = "IDLE"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
