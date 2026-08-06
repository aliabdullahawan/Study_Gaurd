from enum import Enum


class SessionStatus(Enum):
    MANUAL_STOP = "IDLE"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
