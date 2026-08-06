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

    # --- TRACKING VARIABLES ---
    LONG_CLOSURE_SECONDS = 1.5
    EAR_THRESHOLD = None
    blink_count = 0
    is_currently_closed = False
    eyes_closed_start_time = None

    # --- CALIBRATION STATE MACHINE VARIABLES ---
    # State 0: Initializing (2s)
    # State 1: Screen Calc (3s)
    # State 2: Pause (2s)
    # State 3: Keyboard Calc (3s)
    # State 4: Configuring (2s)
    # State 5: Monitoring (Running)
    calib_state = 0
    
    screen_ear_list = []
    keyboard_ear_list = []

    app_start_time = time.monotonic()
    state_start_time = time.monotonic()  # Tracks how long we've been in the current state

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
                state_elapsed = current_time - state_start_time  # Stopwatch for the current state

                detection_result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if detection_result.face_landmarks:
                    landmarks = detection_result.face_landmarks[0]
                    left_eye_pts = [landmarks[i] for i in LEFT_EYE_INDICES]
                    right_eye_pts = [landmarks[i] for i in RIGHT_EYE_INDICES]
                    
                    left_ear = compute_ear(left_eye_pts, frame.shape[1], frame.shape[0])
                    right_ear = compute_ear(right_eye_pts, frame.shape[1], frame.shape[0])
                    avg_ear = (left_ear + right_ear) / 2.0

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
                        # STATE 1: Look at Screen (3 Seconds)
                        countdown = int(math.ceil(3.0 - state_elapsed))
                        cv2.putText(frame, f"Look at the SCREEN: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                        screen_ear_list.append(avg_ear)
                        if state_elapsed >= 3.0:
                            calib_state = 2
                            state_start_time = current_time

                    elif calib_state == 2:
                        # STATE 2: Pause (2 Seconds)
                        cv2.putText(frame, "Relax... Get ready to look down.", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)
                        if state_elapsed >= 2.0:
                            calib_state = 3
                            state_start_time = current_time

                    elif calib_state == 3:
                        # STATE 3: Look at Keyboard (3 Seconds)
                        countdown = int(math.ceil(3.0 - state_elapsed))
                        cv2.putText(frame, f"Look at 'H' & 'G' on keyboard: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                        keyboard_ear_list.append(avg_ear)
                        if state_elapsed >= 3.0:
                            calib_state = 4
                            state_start_time = current_time

                    elif calib_state == 4:
                        # STATE 4: Configuring and Memory Cleanup (2 Seconds)
                        cv2.putText(frame, "Configuring Data...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                        
                        # Only run the math ONCE during this state
                        if EAR_THRESHOLD is None:
                            screen_avg = sum(screen_ear_list) / len(screen_ear_list) if screen_ear_list else 0.25
                            keyboard_avg = sum(keyboard_ear_list) / len(keyboard_ear_list) if keyboard_ear_list else 0.20
                            
                            # The threshold must be strictly LOWER than the keyboard average!
                            EAR_THRESHOLD = keyboard_avg * 0.85
                            
                            print(f"[INFO] Screen Avg: {screen_avg:.3f} | Keyboard Avg: {keyboard_avg:.3f}")
                            print(f"[INFO] Final Threshold Set To: {EAR_THRESHOLD:.3f}")
                            
                            # MEMORY MANAGEMENT: Clear arrays explicitly to free up RAM
                            del screen_ear_list
                            del keyboard_ear_list

                        if state_elapsed >= 2.0:
                            calib_state = 5 # Move to active monitoring

                    elif calib_state == 5:
                        # STATE 5: Active Monitoring
                        if avg_ear < EAR_THRESHOLD:
                            if not is_currently_closed:
                                is_currently_closed = True
                                eyes_closed_start_time = current_time 
                            else:
                                closure_duration = current_time - eyes_closed_start_time
                                if closure_duration >= LONG_CLOSURE_SECONDS:
                                    cv2.putText(frame, "WARNING: FATIGUE DETECTED!", (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                        else:
                            if is_currently_closed:
                                closure_duration = current_time - eyes_closed_start_time
                                is_currently_closed = False 
                                if closure_duration < LONG_CLOSURE_SECONDS:
                                    blink_count += 1 

                        # Visual Feedback
                        color = (0, 255, 0) if avg_ear > EAR_THRESHOLD else (0, 0, 255)
                        cv2.putText(frame, f"EAR: {avg_ear:.3f} / Thresh: {EAR_THRESHOLD:.3f}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                        cv2.putText(frame, f"Blinks: {blink_count}", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

                cv2.imshow("FocusGuard - Milestone 9 EAR Test", frame)

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()