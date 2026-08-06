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
        return 0

    rotation_matrix, _ = cv2.Rodrigues(rotation_vec)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_matrix)

    # We only care about Pitch (Up/Down) for fatigue
    pitch = angles[0] * 360  
    return pitch

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
    PITCH_DROP_THRESHOLD = 15.0  # e.g., dropping from 90 to 75
    raw_baseline_pitch = None
    
    is_head_dropped = False
    head_drop_start_time = None
    total_head_drops = 0

    calib_state = 0
    pitch_list = []
    
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
                    raw_pitch = get_head_pose(landmarks, w, h)

                    if calib_state == 0:
                        cv2.putText(frame, "Gathering info...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        if state_elapsed >= 2.0:
                            calib_state = 1
                            state_start_time = current_time

                    elif calib_state == 1:
                        countdown = int(math.ceil(3.0 - state_elapsed))
                        cv2.putText(frame, f"Look straight ahead: {countdown}s", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                        pitch_list.append(raw_pitch)
                        if state_elapsed >= 3.0:
                            calib_state = 2
                            state_start_time = current_time

                    elif calib_state == 2:
                        cv2.putText(frame, "Configuring Posture...", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                        if raw_baseline_pitch is None:
                            raw_baseline_pitch = sum(pitch_list) / len(pitch_list) if pitch_list else 0.0
                            del pitch_list
                        if state_elapsed >= 2.0:
                            calib_state = 3

                    elif calib_state == 3:
                        # ==========================================
                        # THE 90-DEGREE DIAL LOGIC
                        # ==========================================
                        # 1. Find how much the head moved from the baseline
                        pitch_change = raw_pitch - raw_baseline_pitch
                        
                        # 2. Apply it to a perfect 90-degree straight line
                        # (Note: If looking down makes your angle go up based on your webcam, change to 90 - pitch_change)
                        mapped_pitch = 90.0 + pitch_change
                        
                        # 3. Bug Fix: If OpenCV flips out because the head dropped too far, mapped_pitch jumps wildly.
                        # We force it to register as a drop if it goes wildly out of bounds.
                        is_dropping = False
                        if mapped_pitch < (90.0 - PITCH_DROP_THRESHOLD):
                            is_dropping = True
                        elif mapped_pitch < 0 or mapped_pitch > 150: # The safety catch for the flip bug!
                            is_dropping = True 

                        if is_dropping:
                            if not is_head_dropped:
                                is_head_dropped = True
                                head_drop_start_time = current_time
                            else:
                                drop_duration = current_time - head_drop_start_time
                                if drop_duration >= HEAD_DROP_SECONDS:
                                    cv2.putText(frame, "WARNING: SUSTAINED HEAD DROP!", (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                        else:
                            if is_head_dropped:
                                drop_duration = current_time - head_drop_start_time
                                is_head_dropped = False
                                if drop_duration >= HEAD_DROP_SECONDS:
                                    total_head_drops += 1

                        color = (0, 0, 255) if is_dropping else (0, 255, 0)
                        cv2.putText(frame, f"Head Angle: {mapped_pitch:.1f} (90 is straight)", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                        cv2.putText(frame, f"Head Drops: {total_head_drops}", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

                cv2.imshow("FocusGuard - Milestone 11 Head Pose", frame)
                if cv2.waitKey(5) & 0xFF == ord('q'): break
        finally:
            cap.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()