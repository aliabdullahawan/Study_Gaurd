import time
import cv2
from constants.path import FACE_LANDMARKER_PATH
from core.config_manager import load_or_create_user_config
from core.session_controller import SessionController
from database.database import initialize_database

def main():
    print("=== FocusGuard Startup ===")
    
    # 1. Prepare Database Schema
    initialize_database()

# 2. Load Persistent Profile
    user_baseline, user_prefs = load_or_create_user_config(FACE_LANDMARKER_PATH)
    if not user_baseline:
        print("[ERROR] Configuration/Calibration failed. Exiting.")
        return

    print(f"\n[CONFIG] Profile Loaded Successfully!")
    print(f" -> Inactivity Limit: {user_prefs['inactivity_threshold_sec']} seconds")
    print(f" -> Mouse Distance Threshold: {user_prefs['mouse_distance_threshold']}px")
    print(f" -> Mouse Clicks Threshold: {user_prefs['mouse_click_threshold']} clicks")

    # 3. Ask for study duration for THIS specific session
    try:
        session_mins = float(input("\nEnter study session duration (in minutes): "))
    except ValueError:
        session_mins = 5.0

    session_config = {
        'session_mins': session_mins,
        'alarm_mins': user_prefs['inactivity_threshold_sec'] / 60.0,
        'base_distance': user_prefs['mouse_distance_threshold'],
        'base_clicks': user_prefs['mouse_click_threshold'],
        'alarm_cooldown_sec': user_prefs['alarm_cooldown_sec']
    }

    # 4. Initialize Master Controller (Passing user_baseline object to VisionEngine!)
    controller = SessionController(user_baseline, session_config)

    # 5. UI Feedback Callback (Shows Camera Window & Prints Telemetry)
    def live_ui_feedback(report, frame):
        cv2.imshow("FocusGuard Live Telemetry", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            controller.stop_session(reason="USER_QUIT_WINDOW")

        state = report.get('state', 'UNKNOWN')
        score = report.get('score', 0)
        reason = report.get('explanation', 'Normal activity')
        print(f"[AI BRAIN] State: {state:<12} | Score: {score:<3} | Reason: {reason}")

    # 6. Start Session
    print("\n[SYSTEM] Starting session and camera feed...")
    print("[SYSTEM] Press 'q' in the video window or Ctrl+C in terminal to stop.\n")
    
    controller.start_session(ui_callback=live_ui_feedback)

    # 7. Main loop heartbeat
    try:
        while controller.is_running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n[SYSTEM] Ctrl+C Detected. Shutting down...")
        controller.stop_session(reason="MANUAL_STOP")
    finally:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()