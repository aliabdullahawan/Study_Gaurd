import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Adjust imports based on your actual file structure
from src.constants.path import FACE_LANDMARKER_PATH
from src.vision.calibration import run_live_calibration
from src.vision.vision_engine import VisionEngine  

def main():
    print("[INFO] Starting FocusGuard Vision System...")

    # ==========================================
    # STEP 1: THE SETUP (CALIBRATION)
    # ==========================================
    print("[INFO] Launching Calibration Interface...")
    user_baseline = run_live_calibration(FACE_LANDMARKER_PATH)

    if user_baseline is None:
        print("[ERROR] Calibration failed or was closed early.")
        return

    # Prove we captured the data!
    print("\n[SUCCESS] Baseline Configured:")
    print(f"EAR Thresh: {user_baseline.ear_threshold:.3f}")
    print(f"MAR Thresh: {user_baseline.mar_threshold:.3f}")
    print(f"Pitch Limit: {user_baseline.pitch_limit:.1f}")

    # ==========================================
    # STEP 2: INITIALIZE THE ENGINE
    # ==========================================
    engine = VisionEngine(user_baseline)

    # ==========================================
    # STEP 3: ACTIVE MONITORING LOOP
    # ==========================================
    print("\n[INFO] Starting Active Monitoring... Press 'q' to quit.")
    
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=FACE_LANDMARKER_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1
    )

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    app_start = time.monotonic()

    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            curr_time = time.monotonic()
            timestamp_ms = int((curr_time - app_start) * 1000)

            # Let MediaPipe find the face...
            results = landmarker.detect_for_video(mp_image, timestamp_ms)

            if results.face_landmarks:
                landmarks = results.face_landmarks[0]
                
                # ...and let our VisionEngine do the math!
                snapshot = engine.process_landmarks(landmarks, w, h, curr_time)
                
                # Draw the debug visuals directly onto the frame
                frame = engine.draw_debug_visuals(frame, snapshot)

            cv2.imshow("FocusGuard - Live Vision Engine", frame)
            
            if cv2.waitKey(5) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()