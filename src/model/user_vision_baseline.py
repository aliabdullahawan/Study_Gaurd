from dataclasses import dataclass

@dataclass
class UserVisionBaseline:
    # Eyes
    ear_threshold: float
    # Mouth
    mar_threshold: float
    # Head Posture
    # The exact angles of your head when you sit perfectly straight.
    base_pitch: float
    base_yaw: float
    base_roll: float
    # The maximum allowed deviation from your base angles before triggering a posture warning.
    pitch_limit: float
    yaw_limit: float
    roll_limit: float