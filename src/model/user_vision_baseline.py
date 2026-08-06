from dataclasses import dataclass

@dataclass
class UserVisionBaseline:
    # Eyes
    ear_threshold: float
    # Mouth
    mar_threshold: float
    # Head Posture
    base_pitch: float
    base_yaw: float
    base_roll: float
    pitch_limit: float
    yaw_limit: float
    roll_limit: float