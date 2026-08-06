import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Adjust imports based on your actual file structure
from src.constants.path import FACE_LANDMARKER_PATH
from src.vision.calibration import run_live_calibration
from src.vision.vision_engine import VisionEngine  
from src.monitor.fatigue_engine import FatigueDecisionEngine

def main():
    print("[INFO] Starting FocusGuard Fatigue System...")

    # 1. CALIBRATE VISION
    print("[INFO] Launching Calibration Interface...")
    user_baseline = run_live_calibration(FACE_LANDMARKER_PATH)

    if user_baseline is None:
        print("[ERROR] Calibration failed or was closed early.")
        return

    # 2. INITIALIZE THE ENGINES
    vision_engine = VisionEngine(user_baseline)
    fatigue_engine = FatigueDecisionEngine()

    # 3. SETUP MEDIAPIPE
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=FACE_LANDMARKER_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1
    )

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    app_start = time.monotonic()
    
    # We only want to evaluate the fatigue score once every second, not 30 times a second.
    last_eval_time = time.time()

    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            success, frame = cap.read()
            if not success: break

            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            curr_time = time.monotonic()
            timestamp_ms = int((curr_time - app_start) * 1000)

            # Get the Vision Snapshot
            results = landmarker.detect_for_video(mp_image, timestamp_ms)
            snapshot = None
            
            if results.face_landmarks:
                landmarks = results.face_landmarks[0]
                snapshot = vision_engine.process_landmarks(landmarks, w, h, curr_time)
                frame = vision_engine.draw_debug_visuals(frame, snapshot)

            # --- HARDWARE SIMULATION ---
            # cv2.waitKey returns 255 if nothing is pressed. 
            # If you press any key while the window is active, it registers as activity!
            key = cv2.waitKey(5) & 0xFF
            keyboard_active = (key != 255) 

            # --- THE FATIGUE DECISION ENGINE ---
            # Run the brain every 1 second (so the score doesn't explode instantly)
            current_clock = time.time()
            if snapshot and (current_clock - last_eval_time) >= 1.0:
                # We pretend mouse is False, and use our OpenCV key trick for keyboard
                report = fatigue_engine.evaluate_state(snapshot, mouse_active=False, keyboard_active=keyboard_active)
                last_eval_time = current_clock
                
                # Print the live brain activity to your terminal!
                print(f"STATE: {report['state']} | SCORE: {report['score']} | REASON: {report['explanation']}")

                # Paint the brain's decision on the camera frame too
                cv2.putText(frame, f"STATE: {report['state']}", (10, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 2)
                cv2.putText(frame, f"SCORE: {report['score']}", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 2)

            cv2.imshow("FocusGuard - Fatigue Brain Test", frame)
            
            if key == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()