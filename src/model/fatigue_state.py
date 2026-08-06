from enum import Enum

class FatigueState(Enum):
    NORMAL = "NORMAL"
    POSSIBLY_FATIGUED = "POSSIBLY_FATIGUED"
    DROWSY = "DROWSY"
    ALERTING = "ALERTING"
    COOLDOWN = "COOLDOWN"
