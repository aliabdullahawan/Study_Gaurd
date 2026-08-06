import sqlite3
from datetime import datetime
from constants.path import DB_FILE
from vision.calibration import run_live_calibration

class UserVisionBaseline:
    """Helper class to match the dot-notation expected by VisionEngine."""
    def __init__(self, row_or_dict):
        if isinstance(row_or_dict, dict):
            self.ear_threshold = row_or_dict['ear_threshold']
            self.mar_threshold = row_or_dict['mar_threshold']
            self.base_pitch = row_or_dict['base_pitch']
            self.base_yaw = row_or_dict['base_yaw']
            self.base_roll = row_or_dict['base_roll']
            self.pitch_limit = row_or_dict['pitch_limit']
            self.yaw_limit = row_or_dict['yaw_limit']
            self.roll_limit = row_or_dict['roll_limit']
        else:
            self.ear_threshold = row_or_dict[1]
            self.mar_threshold = row_or_dict[2]
            self.base_pitch = row_or_dict[3]
            self.base_yaw = row_or_dict[4]
            self.base_roll = row_or_dict[5]
            self.pitch_limit = row_or_dict[6]
            self.yaw_limit = row_or_dict[7]
            self.roll_limit = row_or_dict[8]

def load_or_create_user_config(landmarker_path):
    """
    Checks SQLite for existing configuration. Prompts user if they want to reset.
    Returns a tuple: (UserVisionBaseline object, session preferences dict)
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_calibration WHERE id = 1;")
    row = cursor.fetchone()
    conn.close()
    
    # If config exists in DB, ask if user wants to reset it
    if row:
        choice = input("Existing calibration and configuration found. Do you want to reset/re-calibrate? (y/n): ").strip().lower()
        if choice == 'y':
            print("[SYSTEM] Resetting calibration and configuration...")
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_calibration WHERE id = 1;")
                conn.commit()
            row = None  # Forces the setup wizard to run below
        else:
            print("[SYSTEM] Loading existing user configuration from database...")
            baseline = UserVisionBaseline(row)
            preferences = {
                'eye_closure_threshold_sec': row[9],
                'inactivity_threshold_sec': row[10],
                'mouse_distance_threshold': row[11],
                'mouse_click_threshold': row[12],
                'alarm_cooldown_sec': row[13]
            }
            return baseline, preferences

    # Otherwise (or if reset was chosen), run the setup wizard & calibration
    print("[SYSTEM] Running Setup & Calibration Wizard...")
    
    raw_baseline = run_live_calibration(landmarker_path)
    if not raw_baseline:
        return None, None

    print("\n--- Custom Threshold Setup ---")
    try:
        eye_close_mins = float(input("Enter eye closure time (in minutes) before alarm triggers: "))
        inactivity_mins = float(input("Enter keyboard/mouse inactivity time (in minutes) before alarm triggers: "))
        mouse_dist = float(input("Enter mouse movement distance threshold to dismiss alarm (px): "))
        mouse_clicks = int(input("Enter mouse click threshold to dismiss alarm: "))
        cooldown_mins = float(input("Enter alarm cooldown / silence period after dismissal (in minutes): "))
    except ValueError:
        print("Invalid input. Applying smart defaults.")
        eye_close_mins = 0.25
        inactivity_mins = 0.5
        mouse_dist = 500.0
        mouse_clicks = 25
        cooldown_mins = 1.0  # Default 1 minute cooldown

    config_dict = {
        'ear_threshold': raw_baseline.ear_threshold,
        'mar_threshold': raw_baseline.mar_threshold,
        'base_pitch': raw_baseline.base_pitch,
        'base_yaw': raw_baseline.base_yaw,
        'base_roll': raw_baseline.base_roll,
        'pitch_limit': raw_baseline.pitch_limit,
        'yaw_limit': raw_baseline.yaw_limit,
        'roll_limit': raw_baseline.roll_limit,
        'eye_closure_threshold_sec': eye_close_mins * 60,
        'inactivity_threshold_sec': inactivity_mins * 60,
        'mouse_distance_threshold': max(500.0, mouse_dist),
        'mouse_click_threshold': max(25, mouse_clicks),
        'alarm_cooldown_sec': cooldown_mins * 60
    }

    # Save fresh config to SQLite
# Save fresh config to SQLite (FIXED with 14 placeholders for 14 columns)
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_calibration (
                id, ear_threshold, mar_threshold, base_pitch, base_yaw, base_roll,
                pitch_limit, yaw_limit, roll_limit, eye_closure_threshold_sec,
                inactivity_threshold_sec, mouse_distance_threshold, mouse_click_threshold, 
                alarm_cooldown_sec, last_updated
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            config_dict['ear_threshold'], config_dict['mar_threshold'], config_dict['base_pitch'],
            config_dict['base_yaw'], config_dict['base_roll'], config_dict['pitch_limit'],
            config_dict['yaw_limit'], config_dict['roll_limit'], config_dict['eye_closure_threshold_sec'],
            config_dict['inactivity_threshold_sec'], config_dict['mouse_distance_threshold'],
            config_dict['mouse_click_threshold'], config_dict['alarm_cooldown_sec'],
            datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        ))
        conn.commit()

    print("[SYSTEM] Configuration saved successfully to database!")
    return UserVisionBaseline(config_dict), {
        'eye_closure_threshold_sec': config_dict['eye_closure_threshold_sec'],
        'inactivity_threshold_sec': config_dict['inactivity_threshold_sec'],
        'mouse_distance_threshold': config_dict['mouse_distance_threshold'],
        'mouse_click_threshold': config_dict['mouse_click_threshold'],
        'alarm_cooldown_sec': config_dict['alarm_cooldown_sec'] # <--- Added here
    }