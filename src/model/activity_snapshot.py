from dataclasses import dataclass


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