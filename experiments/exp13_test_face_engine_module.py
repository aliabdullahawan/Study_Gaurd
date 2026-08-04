import cv2
import sys
import os

# Add src to path so we can import our new module cleanly
ROOT_DIR = sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from vision import face_engine

def main():
    print("[INFO] Initializing FaceLandmarkEngine module...")
    engine = face_engine.FaceLandmarkEngine()
    
    # Starting frame captuere and setting up correct drivers
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    print("[INFO] Camera running. Look away from the camera to test face-missing tracking. Press 'q' to quit.")

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            # Process frame through our modular engine
            result = engine.process_frame(frame)

            # Print status if face is missing for more than 1 second
            if not result["face_detected"]:
                print(f"[WARNING] Face missing for {result['face_missing_seconds']} seconds!", end="\r")

            cv2.imshow("FocusGuard - Phase 8 Modular Test", result["annotated_frame"])

            if cv2.waitKey(5) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        engine.close()
        print("\n[INFO] Test completed cleanly.")

if __name__ == "__main__":
    main()