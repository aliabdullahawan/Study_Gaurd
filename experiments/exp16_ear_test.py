import os
import sys
import cv2
import time
import math
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]

def calculate_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def compute_ear(eye_landmarks, frame_width, frame_height):
    p1 = eye_landmarks[0]
    p4 = eye_landmarks[3]
    p2 = eye_landmarks[1]
    p6 = eye_landmarks[5]
    p3 = eye_landmarks[2]
    p5 = eye_landmarks[4]

    vertical_1 = calculate_distance(p2, p6)
    vertical_2 = calculate_distance(p3, p5)
    horizontal = calculate_distance(p1, p4)

    if horizontal == 0.0:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.abspath(os.path.join(script_dir, "..", "assets", "FaceLandMarks", "face_landmarker.task"))
    
    if not os.path.exists(model_path):
        model_path = os.path.abspath(os.path.join(script_dir, "face_landmarker.task"))

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

    # --- TRACKING & CALIBRATION VARIABLES ---
    LONG_CLOSURE_SECONDS = 1.5
    
    # Calibration States
    is_calibrating = True
    calibration_duration = 3.0 # seconds
    baseline_ear_list = []     # Store EAR scores during calibration
    EAR_THRESHOLD = None       # Will be set dynamically after calibration
    EAR_MULTIPLIER = 0.60     # Threshold will be 75% of your normal open-eye score
    
    # Blink States
    blink_count = 0
    is_currently_closed = False
    eyes_closed_start_time = None

    app_start_time = time.monotonic()
    print("[INFO] Camera active. Look normally at the camera for calibration...")

    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        try:
            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    break

                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                
                current_time = time.monotonic()
                timestamp_ms = int((current_time - app_start_time) * 1000)

                detection_result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if detection_result.face_landmarks:
                    landmarks = detection_result.face_landmarks[0]
                    
                    left_eye_pts = [landmarks[i] for i in LEFT_EYE_INDICES]
                    right_eye_pts = [landmarks[i] for i in RIGHT_EYE_INDICES]

                    left_ear = compute_ear(left_eye_pts, frame.shape[1], frame.shape[0])
                    right_ear = compute_ear(right_eye_pts, frame.shape[1], frame.shape[0])
                    avg_ear = (left_ear + right_ear) / 2.0

                    # ==========================================
                    # PHASE 1: CALIBRATION
                    # ==========================================
                    if is_calibrating:
                        elapsed_calib_time = current_time - app_start_time
                        
                        if elapsed_calib_time < calibration_duration:
                            # Collect data
                            baseline_ear_list.append(avg_ear)
                            cv2.putText(frame, "CALIBRATING... Look at camera", (30, 50), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        else:
                            # Time is up! Calculate the personal threshold
                            if len(baseline_ear_list) > 0:
                                personal_baseline = sum(baseline_ear_list) / len(baseline_ear_list)
                                EAR_THRESHOLD = personal_baseline * EAR_MULTIPLIER
                                print(f"[SUCCESS] Calibration complete! Baseline: {personal_baseline:.3f}, Threshold: {EAR_THRESHOLD:.3f}")
                            else:
                                # Fallback just in case face wasn't found during those 3 seconds
                                EAR_THRESHOLD = 0.20 
                            
                            is_calibrating = False # End calibration phase

                    # ==========================================
                    # PHASE 2: MONITORING (Only runs after calibration)
                    # ==========================================
                    else:
                        if avg_ear < EAR_THRESHOLD:
                            if not is_currently_closed:
                                is_currently_closed = True
                                eyes_closed_start_time = current_time 
                            else:
                                closure_duration = current_time - eyes_closed_start_time
                                if closure_duration >= LONG_CLOSURE_SECONDS:
                                    cv2.putText(frame, "WARNING: FATIGUE DETECTED!", (30, 130), 
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                        else:
                            if is_currently_closed:
                                closure_duration = current_time - eyes_closed_start_time
                                is_currently_closed = False 
                                
                                if closure_duration < LONG_CLOSURE_SECONDS:
                                    blink_count += 1 

                        # Visual Feedback
                        color = (0, 255, 0) if avg_ear > EAR_THRESHOLD else (0, 0, 255)
                        cv2.putText(frame, f"EAR: {avg_ear:.3f} / Thresh: {EAR_THRESHOLD:.3f}", (30, 50), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                        cv2.putText(frame, f"Blinks: {blink_count}", (30, 90), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

                cv2.imshow("FocusGuard - Milestone 9 EAR Test", frame)

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()