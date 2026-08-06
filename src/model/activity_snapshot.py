from dataclasses import dataclass
from typing import Optional



@dataclass
class ActivitySnapshot:
    session_id: str
    timestamp: str
    
    # --- HARDWARE METRICS ---
    is_active: bool
    mouse_distance_pixels: float
    mouse_click_count: int
    mouse_scroll_count: int
    key_press_count: int
    inactivity_seconds: float
    inactivity_triggered: bool
    
    # --- VISION METRICS (Optional because face might be out of frame) ---
    ear: Optional[float] = None
    mar: Optional[float] = None
    pitch: Optional[float] = None
    yaw: Optional[float] = None
    roll: Optional[float] = None
    
    # --- FATIGUE METRICS ---
    total_blinks: int = 0
    total_yawns: int = 0
    total_posture_warnings: int = 0
    fatigue_score: int = 0
    fatigue_state: str = "NORMAL"