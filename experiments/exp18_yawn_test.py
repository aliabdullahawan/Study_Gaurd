import os
import sys
import cv2
import time
import math
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# MOUTH INDICES: 78 (Left corner), 308 (Right corner), 13 (Upper inner lip), 14 (Lower inner lip)
MOUTH_INDICES = [78, 308, 13, 14]

def calculate_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def compute_mar(mouth_landmarks):
    """
    Computes the Mouth Aspect Ratio (MAR).
    Inverse of EAR: Value goes UP when the mouth opens.
    """
    p1 = mouth_landmarks[0] # Left corner
    p2 = mouth_landmarks[1] # Right corner
    p3 = mouth_landmarks[2] # Top inner lip
    p4 = mouth_landmarks[3] # Bottom inner lip

    horizontal = calculate_distance(p1, p2)
    vertical = calculate_distance(p3, p4)

    if horizontal == 0.0:
        return 0.0
    
    # MAR formula: vertical distance / horizontal distance
    return vertical / horizontal

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

    # --- TRACKING VARIABLES ---
    YAWN_MIN_SECONDS = 3.5  # Mouth must be wide open for at least 3.5s to be a yawn
    MAR_THRESHOLD = None
    yawn_count = 0
    is_currently_open = False
    mouth_open_start_time = None

    # --- CALIBRATION STATE MACHINE VARIABLES ---
    calib_state = 0
    relaxed_mar_list = []
    talking_mar_list = []

    app_start_time = time.monotonic()
    state_start_time = time.monotonic() 

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
                state_elapsed = current_time - state_start_time 

                detection_result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if detection_result.face_landmarks:
                    landmarks = detection_result.face_landmarks[0]
                    mouth_pts = [landmarks[i] for i in MOUTH_INDICES]
                    
                    mar = compute_mar(mouth_pts)

                    # ==========================================
                    # THE CALIBRATION STATE MACHINE
                    # ==========================================
                    
                    if calib_state == 0:
                        # STATE 0: Gathering Info Delay (2 Seconds)
                        cv2.putText(frame, "Gathering info... Please wait.", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        if state_elapsed >= 2.0:
                            calib_state = 1
                            state_start_time = current_time

                    elif calib_state == 1:
                        # STATE 1: Keep mouth CLOSED (3 Seconds)
                        countdown = int(math.ceil(3.0 - state_elapsed))
                        cv2.putText(frame, f"Keep mouth CLOSED & RELAXED: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                        relaxed_mar_list.append(mar)
                        if state_elapsed >= 3.0:
                            calib_state = 2
                            state_start_time = current_time

                    elif calib_state == 2:
                        # STATE 2: Pause (2 Seconds)
                        cv2.putText(frame, "Relax... Get ready to talk.", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)
                        if state_elapsed >= 2.0:
                            calib_state = 3
                            state_start_time = current_time

                    elif calib_state == 3:
                        # STATE 3: Read / Talk naturally (3 Seconds)
                        countdown = int(math.ceil(3.0 - state_elapsed))
                        cv2.putText(frame, f"Read out loud / TALK naturally: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                        talking_mar_list.append(mar)
                        if state_elapsed >= 3.0:
                            calib_state = 4
                            state_start_time = current_time

                    elif calib_state == 4:
                        # STATE 4: Configuring and Memory Cleanup (2 Seconds)
                        cv2.putText(frame, "Configuring Yawn Data...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                        
                        if MAR_THRESHOLD is None:
                            relaxed_avg = sum(relaxed_mar_list) / len(relaxed_mar_list) if relaxed_mar_list else 0.02
                            talking_avg = sum(talking_mar_list) / len(talking_mar_list) if talking_mar_list else 0.10
                            
                            # The yawn threshold must be significantly HIGHER than the talking average!
                            MAR_THRESHOLD = talking_avg * 1.8 
                            
                            print(f"[INFO] Relaxed Avg: {relaxed_avg:.3f} | Talking Avg: {talking_avg:.3f}")
                            print(f"[INFO] Yawn Threshold Set To: {MAR_THRESHOLD:.3f}")
                            
                            del relaxed_mar_list
                            del talking_mar_list

                        if state_elapsed >= 2.0:
                            calib_state = 5

                    elif calib_state == 5:
                        # STATE 5: Active Monitoring (Inverse Logic!)
                        
                        if mar > MAR_THRESHOLD:  # <--- LOGIC INVERTED HERE
                            if not is_currently_open:
                                is_currently_open = True
                                mouth_open_start_time = current_time 
                            else:
                                open_duration = current_time - mouth_open_start_time
                                if open_duration >= YAWN_MIN_SECONDS:
                                    cv2.putText(frame, "WARNING: YAWN DETECTED!", (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                        else:
                            if is_currently_open:
                                open_duration = current_time - mouth_open_start_time
                                is_currently_open = False 
                                
                                # If it was open for a long time, it was a yawn! (Not just talking)
                                if open_duration >= YAWN_MIN_SECONDS:
                                    yawn_count += 1 

                        # Visual Feedback
                        color = (0, 0, 255) if mar > MAR_THRESHOLD else (0, 255, 0)
                        cv2.putText(frame, f"MAR: {mar:.3f} / Thresh: {MAR_THRESHOLD:.3f}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                        cv2.putText(frame, f"Yawns: {yawn_count}", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

                cv2.imshow("FocusGuard - Milestone 10 Yawn Test", frame)

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()