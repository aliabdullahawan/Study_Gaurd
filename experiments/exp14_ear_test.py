import os
import sys
import cv2
import time
import math
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Landmark indices for Left and Right eyes in MediaPipe Face Mesh
# These map out the corners and top/bottom eyelids
LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]

def calculate_distance(p1, p2):
    """Calculates the Euclidean distance between two 2D/3D landmark points."""
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def compute_ear(eye_landmarks, frame_width, frame_height):
    """
    Computes the Eye Aspect Ratio (EAR) for a single eye.
    """
    # p1 and p4 are the horizontal corners (outer and inner)
    p1 = eye_landmarks[0]
    p4 = eye_landmarks[3]
    
    # p2, p6 and p3, p5 are the vertical upper/lower eyelid pairs
    p2 = eye_landmarks[1]
    p6 = eye_landmarks[5]
    p3 = eye_landmarks[2]
    p5 = eye_landmarks[4]

    # Calculate vertical distances
    vertical_1 = calculate_distance(p2, p6)
    vertical_2 = calculate_distance(p3, p5)

    # Calculate horizontal distance
    horizontal = calculate_distance(p1, p4)

    # Avoid division by zero
    if horizontal == 0.0:
        return 0.0

    # Apply the EAR formula
    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
    return ear

def main():
    # Resolve model path safely from experiments folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.abspath(os.path.join(script_dir, "..", "assets", "FaceLandMarks", "face_landmarker.task"))
    
    if not os.path.exists(model_path):
        # Fallback to root directory if needed
        model_path = os.path.abspath(os.path.join(script_dir, "face_landmarker.task"))
        if not os.path.exists(model_path):
            print(f"[ERROR] Model file not found at: {model_path}")

    print("[INFO] Initializing FaceLandmarker for EAR tracking...")
    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1
    )

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    start_time = time.monotonic()
    
    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        print("[INFO] Camera active. Blink your eyes and watch the EAR score change in the terminal/window. Press 'q' to quit.")
        try:
            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    break

                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                timestamp_ms = int((time.monotonic() - start_time) * 1000)

                detection_result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if detection_result.face_landmarks:
                    landmarks = detection_result.face_landmarks[0]
                    
                    # Extract specific points for left and right eyes
                    left_eye_pts = [landmarks[i] for i in LEFT_EYE_INDICES]
                    right_eye_pts = [landmarks[i] for i in RIGHT_EYE_INDICES]

                    # Calculate EAR for both eyes
                    left_ear = compute_ear(left_eye_pts, frame.shape[1], frame.shape[0])
                    right_ear = compute_ear(right_eye_pts, frame.shape[1], frame.shape[0])
                    
                    # Average EAR of both eyes
                    avg_ear = (left_ear + right_ear) / 2.0

                    # Display the EAR score live on the video frame
                    color = (0, 255, 0) if avg_ear > 0.20 else (0, 0, 255) # Turns red if eyes close!
                    cv2.putText(frame, f"EAR: {avg_ear:.3f}", (30, 50), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

                cv2.imshow("FocusGuard - Milestone 9 EAR Test", frame)

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()
            print("[INFO] EAR test completed.")

if __name__ == "__main__":
    main()