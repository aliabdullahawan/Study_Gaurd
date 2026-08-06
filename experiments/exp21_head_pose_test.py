import os
import sys
import cv2
import time
import math
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

POSE_INDICES = [1, 152, 33, 263, 61, 291]

FACE_3D_MODEL_POINTS = np.array([
    (0.0, 0.0, 0.0),             
    (0.0, -330.0, -65.0),        
    (-225.0, 170.0, -135.0),     
    (225.0, 170.0, -135.0),      
    (-150.0, -150.0, -125.0),    
    (150.0, -150.0, -125.0)      
], dtype=np.float64)

def get_head_pose(landmarks, frame_width, frame_height):
    """Returns raw Pitch (Up/Down), Yaw (Left/Right), and Roll (Tilt)"""
    image_points = np.array([
        (landmarks[1].x * frame_width, landmarks[1].y * frame_height),
        (landmarks[152].x * frame_width, landmarks[152].y * frame_height),
        (landmarks[33].x * frame_width, landmarks[33].y * frame_height),
        (landmarks[263].x * frame_width, landmarks[263].y * frame_height),
        (landmarks[61].x * frame_width, landmarks[61].y * frame_height),
        (landmarks[291].x * frame_width, landmarks[291].y * frame_height)
    ], dtype=np.float64)

    focal_length = frame_width
    center = (frame_width / 2, frame_height / 2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1))

    success, rotation_vec, translation_vec = cv2.solvePnP(
        FACE_3D_MODEL_POINTS, image_points, camera_matrix, dist_coeffs
    )

    if not success:
        return 0, 0, 0

    rotation_matrix, _ = cv2.Rodrigues(rotation_vec)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_matrix)

    pitch = angles[0] * 360  
    yaw = angles[1] * 360
    roll = angles[2] * 360
    
    return pitch, yaw, roll

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

    # --- TRACKING VARIABLES ---
    HEAD_DROP_SECONDS = 3.0
    
    # Baselines (Looking straight)
    base_p, base_y, base_r = None, None, None
    
    # Custom thresholds (Calculated during State 3)
    thresh_p, thresh_y, thresh_r = None, None, None
    
    is_bad_posture = False
    bad_posture_start_time = None
    total_posture_warnings = 0

    calib_state = 0
    
    # Data collection lists
    straight_p, straight_y, straight_r = [], [], []
    limit_p, limit_y, limit_r = [], [], []
    
    app_start_time = time.monotonic()
    state_start_time = time.monotonic() 

    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        try:
            while cap.isOpened():
                success, frame = cap.read()
                if not success: break
                
                h, w, _ = frame.shape
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                
                current_time = time.monotonic()
                timestamp_ms = int((current_time - app_start_time) * 1000)
                state_elapsed = current_time - state_start_time 

                detection_result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if detection_result.face_landmarks:
                    landmarks = detection_result.face_landmarks[0]
                    raw_p, raw_y, raw_r = get_head_pose(landmarks, w, h)

                    # Always display raw angles at the top right so you can see the math live
                    cv2.putText(frame, f"RAW | P: {raw_p:.0f} Y: {raw_y:.0f} R: {raw_r:.0f}", (w - 350, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                    # ==========================================
                    # MULTI-STAGE CALIBRATION
                    # ==========================================
                    if calib_state == 0:
                        cv2.putText(frame, "Gathering info...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        if state_elapsed >= 2.0:
                            calib_state = 1
                            state_start_time = current_time

                    elif calib_state == 1:
                        countdown = int(math.ceil(3.0 - state_elapsed))
                        cv2.putText(frame, f"Look straight ahead: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                        straight_p.append(raw_p)
                        straight_y.append(raw_y)
                        straight_r.append(raw_r)
                        if state_elapsed >= 3.0:
                            calib_state = 2
                            state_start_time = current_time

                    elif calib_state == 2:
                        cv2.putText(frame, "Get ready to set your tilt limits...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)
                        if base_p is None:
                            # Calculate exactly what "straight" means for you
                            base_p = sum(straight_p) / len(straight_p) if straight_p else 0
                            base_y = sum(straight_y) / len(straight_y) if straight_y else 0
                            base_r = sum(straight_r) / len(straight_r) if straight_r else 0
                            del straight_p, straight_y, straight_r
                        if state_elapsed >= 2.0:
                            calib_state = 3
                            state_start_time = current_time

                    elif calib_state == 3:
                        countdown = int(math.ceil(4.0 - state_elapsed))
                        # Ask the user to physically demonstrate the limits
                        cv2.putText(frame, f"Tilt head DOWN, LEFT, and RIGHT: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        limit_p.append(raw_p)
                        limit_y.append(raw_y)
                        limit_r.append(raw_r)
                        if state_elapsed >= 4.0:
                            calib_state = 4
                            state_start_time = current_time

                    elif calib_state == 4:
                        cv2.putText(frame, "Calculating your custom thresholds...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                        if thresh_p is None:
                            # Find the absolute MAXIMUM deviation you made during the limit test
                            # We enforce a minimum of 15 degrees just in case you didn't move much
                            max_p_dev = max([abs(p - base_p) for p in limit_p]) if limit_p else 0
                            max_y_dev = max([abs(y - base_y) for y in limit_y]) if limit_y else 0
                            max_r_dev = max([abs(r - base_r) for r in limit_r]) if limit_r else 0
                            
                            thresh_p = max(15.0, max_p_dev * 0.9) # 90% of your max tilt
                            thresh_y = max(15.0, max_y_dev * 0.9)
                            thresh_r = max(15.0, max_r_dev * 0.9)
                            
                            print(f"[INFO] Custom Thresholds - Pitch: {thresh_p:.1f} | Yaw: {thresh_y:.1f} | Roll: {thresh_r:.1f}")
                            del limit_p, limit_y, limit_r
                        
                        if state_elapsed >= 2.0:
                            calib_state = 5

                    elif calib_state == 5:
                        # ==========================================
                        # ACTIVE MONITORING WITH CUSTOM LIMITS
                        # ==========================================
                        # Calculate exactly how far you have drifted from your straight baseline
                        dev_p = abs(raw_p - base_p)
                        dev_y = abs(raw_y - base_y)
                        dev_r = abs(raw_r - base_r)
                        
                        # If ANY of the three angles break your personal threshold, it's bad posture
                        is_breaking_limit = (dev_p > thresh_p) or (dev_y > thresh_y) or (dev_r > thresh_r)
                        
                        if is_breaking_limit:
                            if not is_bad_posture:
                                is_bad_posture = True
                                bad_posture_start_time = current_time
                            else:
                                duration = current_time - bad_posture_start_time
                                if duration >= HEAD_DROP_SECONDS:
                                    cv2.putText(frame, "WARNING: BAD POSTURE / HEAD DROP!", (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                        else:
                            if is_bad_posture:
                                duration = current_time - bad_posture_start_time
                                is_bad_posture = False
                                if duration >= HEAD_DROP_SECONDS:
                                    total_posture_warnings += 1

                        # Visual Feedback
                        color = (0, 0, 255) if is_breaking_limit else (0, 255, 0)
                        cv2.putText(frame, f"Deviation -> P: {dev_p:.1f}  Y: {dev_y:.1f}  R: {dev_r:.1f}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                        cv2.putText(frame, f"Posture Warnings: {total_posture_warnings}", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

                cv2.imshow("FocusGuard - Milestone 11 Head Pose", frame)
                if cv2.waitKey(5) & 0xFF == ord('q'): break
        finally:
            cap.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()