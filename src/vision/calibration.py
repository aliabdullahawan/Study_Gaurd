import os
import cv2
import time
import math
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from model.user_vision_baseline import UserVisionBaseline

# --- MEDIA PIPE CONSTANTS ---
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
MOUTH = [78, 308, 13, 14]
POSE = [1, 152, 33, 263, 61, 291]
FACE_3D = np.array([(0.0, 0.0, 0.0), (0.0, -330.0, -65.0), (-225.0, 170.0, -135.0), 
                    (225.0, 170.0, -135.0), (-150.0, -150.0, -125.0), (150.0, -150.0, -125.0)], dtype=np.float64)

# --- MATH HELPERS ---
def get_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def get_ear(landmarks, indices):
    pts = [landmarks[i] for i in indices]
    h = get_distance(pts[0], pts[3])
    if h == 0: return 0.0
    return (get_distance(pts[1], pts[5]) + get_distance(pts[2], pts[4])) / (2.0 * h)

def get_mar(landmarks):
    pts = [landmarks[i] for i in MOUTH]
    h = get_distance(pts[0], pts[1])
    if h == 0: return 0.0
    return get_distance(pts[2], pts[3]) / h

def get_pose(landmarks, w, h):
    img_pts = np.array([(landmarks[i].x * w, landmarks[i].y * h) for i in POSE], dtype=np.float64)
    cam_matrix = np.array([[w, 0, w/2], [0, w, h/2], [0, 0, 1]], dtype=np.float64)
    success, rot_vec, _ = cv2.solvePnP(FACE_3D, img_pts, cam_matrix, np.zeros((4, 1)))
    if not success: return 0, 0, 0
    rot_mat, _ = cv2.Rodrigues(rot_vec)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rot_mat)
    return angles[0]*360, angles[1]*360, angles[2]*360

def run_live_calibration(model_path: str) -> UserVisionBaseline:
    """
    Executes the precise multi-stage timed calibration flow for Eyes, Yawn, and Head Posture.
    """
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1
    )

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    state = 0
    app_start = time.monotonic()
    state_start = time.monotonic()
    
    # Data tracking buckets
    screen_ear_list = []
    keyboard_ear_list = []
    relaxed_mar_list = []
    talking_mar_list = []
    base_p_list, base_y_list, base_r_list = [], [], []
    limit_p, limit_y, limit_r = [], [], []
    
    baseline_data = None

    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            success, frame = cap.read()
            if not success: break
            
            fh, fw, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            curr_time = time.monotonic()
            timestamp_ms = int((curr_time - app_start) * 1000)
            elapsed = curr_time - state_start
            
            results = landmarker.detect_for_video(mp_image, timestamp_ms)

            if results.face_landmarks:
                lms = results.face_landmarks[0]
                ear = (get_ear(lms, LEFT_EYE) + get_ear(lms, RIGHT_EYE)) / 2.0
                mar = get_mar(lms)
                p, y, r = get_pose(lms, fw, fh)

                # ==========================================
                # PRECISE TIMED CALIBRATION STATE MACHINE
                # ==========================================

                # 1. Eye Calibration Prep (2s)
                if state == 0:
                    cv2.putText(frame, "Ready for Eye Calibration...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    if elapsed >= 2.0:
                        state = 1
                        state_start = curr_time

                # 2. Look at Screen (3s)
                elif state == 1:
                    countdown = int(math.ceil(3.0 - elapsed))
                    cv2.putText(frame, f"Look at the SCREEN: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    screen_ear_list.append(ear)
                    if elapsed >= 3.0:
                        state = 2
                        state_start = curr_time

                # 3. Transition / Rest (2s)
                elif state == 2:
                    cv2.putText(frame, "Ready for next calibration...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)
                    if elapsed >= 2.0:
                        state = 3
                        state_start = curr_time

                # 4. Look at 'G' and 'H' on keyboard (3s)
                elif state == 3:
                    countdown = int(math.ceil(3.0 - elapsed))
                    cv2.putText(frame, f"Look at letters 'G' & 'H' on keyboard: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    keyboard_ear_list.append(ear)
                    if elapsed >= 3.0:
                        state = 4
                        state_start = curr_time

                # 5. Yawn Calibration Prep (2s)
                elif state == 4:
                    cv2.putText(frame, "Ready for Yawn Detection Calibration...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    if elapsed >= 2.0:
                        state = 5
                        state_start = curr_time

                # 6. Look normally at camera (3s)
                elif state == 5:
                    countdown = int(math.ceil(3.0 - elapsed))
                    cv2.putText(frame, f"Look normally at camera: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    relaxed_mar_list.append(mar)
                    if elapsed >= 3.0:
                        state = 6
                        state_start = curr_time

                # 7. Rest / Pause (2s)
                elif state == 6:
                    cv2.putText(frame, "Rest / Get ready to talk...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)
                    if elapsed >= 2.0:
                        state = 7
                        state_start = curr_time

                # 8. Talk naturally (3s)
                elif state == 7:
                    countdown = int(math.ceil(3.0 - elapsed))
                    cv2.putText(frame, f"Talk / Read aloud naturally: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    talking_mar_list.append(mar)
                    if elapsed >= 3.0:
                        state = 8
                        state_start = curr_time

                # 9. Head Calibration Prep (2s)
                elif state == 8:
                    cv2.putText(frame, "Ready for Head Calibration...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    if elapsed >= 2.0:
                        state = 9
                        state_start = curr_time

                # 10. Straight up your head (3s)
                elif state == 9:
                    countdown = int(math.ceil(3.0 - elapsed))
                    cv2.putText(frame, f"Straight up your head: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    base_p_list.append(p)
                    base_y_list.append(y)
                    base_r_list.append(r)
                    if elapsed >= 3.0:
                        state = 10
                        state_start = curr_time

                # 11. Rest (2s)
                elif state == 10:
                    cv2.putText(frame, "Rest / Get ready for normal movement...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)
                    if elapsed >= 2.0:
                        state = 11
                        state_start = curr_time

                # 12. Tilt head normal movement limits (5s)
                elif state == 11:
                    countdown = int(math.ceil(5.0 - elapsed))
                    cv2.putText(frame, f"Tilt head normal movement: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                    limit_p.append(p)
                    limit_y.append(y)
                    limit_r.append(r)
                    if elapsed >= 5.0:
                        state = 12
                        state_start = curr_time

                # 13. Finalize and Configure
                elif state == 12:
                    cv2.putText(frame, "All calibrations done! Configuring...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                    cv2.imshow("FocusGuard System Setup", frame)
                    cv2.waitKey(100)
                    
                    # Compute safe math thresholds
                    keyboard_avg = sum(keyboard_ear_list) / len(keyboard_ear_list) if keyboard_ear_list else 0.20
                    final_ear_thresh = keyboard_avg * 0.85
                    
                    talking_avg = sum(talking_mar_list) / len(talking_mar_list) if talking_mar_list else 0.10
                    final_mar_thresh = talking_avg * 1.8
                    
                    b_p = sum(base_p_list) / len(base_p_list) if base_p_list else 0.0
                    b_y = sum(base_y_list) / len(base_y_list) if base_y_list else 0.0
                    b_r = sum(base_r_list) / len(base_r_list) if base_r_list else 0.0
                    
                    t_p = max(15.0, max([abs(val - b_p) for val in limit_p]) * 0.9) if limit_p else 15.0
                    t_y = max(15.0, max([abs(val - b_y) for val in limit_y]) * 0.9) if limit_y else 15.0
                    t_r = max(15.0, max([abs(val - b_r) for val in limit_r]) * 0.9) if limit_r else 15.0
                    
                    baseline_data = UserVisionBaseline(
                        ear_threshold=final_ear_thresh,
                        mar_threshold=final_mar_thresh,
                        base_pitch=b_p, base_yaw=b_y, base_roll=b_r,
                        pitch_limit=t_p, yaw_limit=t_y, roll_limit=t_r
                    )
                    break

            cv2.imshow("FocusGuard System Setup", frame)
            if cv2.waitKey(5) & 0xFF == ord('q'): break
            
    cap.release()
    cv2.destroyAllWindows()
    return baseline_data