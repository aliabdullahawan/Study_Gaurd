import cv2
import time
import math
import numpy as np

# --- MEDIA PIPE CONSTANTS ---
LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
MOUTH = [78, 308, 13, 14]
POSE = [1, 152, 33, 263, 61, 291]
FACE_3D = np.array([(0.0, 0.0, 0.0), (0.0, -330.0, -65.0), (-225.0, 170.0, -135.0), 
                    (225.0, 170.0, -135.0), (-150.0, -150.0, -125.0), (150.0, -150.0, -125.0)], dtype=np.float64)

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


class VisionEngine:
    def __init__(self, baseline_data):
        self.baseline = baseline_data
        
        # Threshold Settings
        self.LONG_CLOSURE_SECONDS = 1.5
        self.YAWN_SECONDS = 3.5
        self.POSTURE_SECONDS = 3.0

        # State Trackers & Counters
        self.is_eyes_closed = False
        self.eyes_closed_start = None
        self.closure_counted = False
        self.total_blinks = 0
        self.total_prolonged_closures = 0
        
        self.is_yawning = False
        self.yawn_start = None
        self.yawn_counted = False
        self.total_yawns = 0
        
        self.is_bad_posture = False
        self.posture_start = None
        self.posture_counted = False
        self.total_posture_warnings = 0

    def process_landmarks(self, landmarks, frame_width, frame_height, current_time):
        """Calculates metrics, updates counters, and checks them against the baseline."""
        ear = (get_ear(landmarks, LEFT_EYE) + get_ear(landmarks, RIGHT_EYE)) / 2.0
        mar = get_mar(landmarks)
        p, y, r = get_pose(landmarks, frame_width, frame_height)
        
        snapshot = {
            "ear": ear,
            "mar": mar,
            "pitch_dev": abs(p - self.baseline.base_pitch),
            "yaw_dev": abs(y - self.baseline.base_yaw),
            "roll_dev": abs(r - self.baseline.base_roll),
            "is_prolonged_closure": False,
            "is_yawning": False,
            "is_bad_posture": False,
            "blink_detected": False
        }

        # --- EYE LOGIC ---
        if ear < self.baseline.ear_threshold:
            if not self.is_eyes_closed:
                self.is_eyes_closed = True
                self.eyes_closed_start = current_time
                self.closure_counted = False
            elif (current_time - self.eyes_closed_start) >= self.LONG_CLOSURE_SECONDS:
                snapshot["is_prolonged_closure"] = True
                if not self.closure_counted:
                    self.total_prolonged_closures += 1
                    self.closure_counted = True
        else:
            if self.is_eyes_closed:
                if (current_time - self.eyes_closed_start) < self.LONG_CLOSURE_SECONDS:
                    snapshot["blink_detected"] = True
                    self.total_blinks += 1
                self.is_eyes_closed = False

        # --- MOUTH LOGIC ---
        if mar > self.baseline.mar_threshold:
            if not self.is_yawning:
                self.is_yawning = True
                self.yawn_start = current_time
                self.yawn_counted = False
            elif (current_time - self.yawn_start) >= self.YAWN_SECONDS:
                snapshot["is_yawning"] = True
                if not self.yawn_counted:
                    self.total_yawns += 1
                    self.yawn_counted = True
        else:
            self.is_yawning = False

        # --- POSTURE LOGIC ---
        is_breaking_limit = (snapshot["pitch_dev"] > self.baseline.pitch_limit) or \
                            (snapshot["yaw_dev"] > self.baseline.yaw_limit) or \
                            (snapshot["roll_dev"] > self.baseline.roll_limit)
                            
        if is_breaking_limit:
            if not self.is_bad_posture:
                self.is_bad_posture = True
                self.posture_start = current_time
                self.posture_counted = False
            elif (current_time - self.posture_start) >= self.POSTURE_SECONDS:
                snapshot["is_bad_posture"] = True
                if not self.posture_counted:
                    self.total_posture_warnings += 1
                    self.posture_counted = True
        else:
            self.is_bad_posture = False

        # Attach final lifetime counters to the snapshot
        snapshot["total_blinks"] = self.total_blinks
        snapshot["total_yawns"] = self.total_yawns
        snapshot["total_posture_warnings"] = self.total_posture_warnings

        return snapshot

    def draw_debug_visuals(self, frame, snapshot):
        """
        Paints live metrics, big red alerts, and lifetime counters on the video frame.
        """
        eye_color = (0, 0, 255) if snapshot["is_prolonged_closure"] else (0, 255, 0)
        yawn_color = (0, 0, 255) if snapshot["is_yawning"] else (0, 255, 0)
        post_color = (0, 0, 255) if snapshot["is_bad_posture"] else (0, 255, 0)

        # Draw Current Real-Time Math
        cv2.putText(frame, f"EAR: {snapshot['ear']:.3f} / Thresh: {self.baseline.ear_threshold:.3f}", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, eye_color, 2)
        cv2.putText(frame, f"MAR: {snapshot['mar']:.3f} / Thresh: {self.baseline.mar_threshold:.3f}", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, yawn_color, 2)
        cv2.putText(frame, f"Pitch Dev: {snapshot['pitch_dev']:.1f} / Limit: {self.baseline.pitch_limit:.1f}", 
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, post_color, 2)

        # Draw the Lifetime Counters (in bright cyan/yellow so they pop)
        cv2.putText(frame, f"Blinks: {snapshot['total_blinks']} | Yawns: {snapshot['total_yawns']} | Head Drops: {snapshot['total_posture_warnings']}", 
                    (10, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # MASSIVE Red Warning Labels
        y_offset = 200
        if snapshot["is_prolonged_closure"]:
            cv2.putText(frame, "ALERT: EYE CLOSING DETECTED!", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
            y_offset += 40
            
        if snapshot["is_yawning"]:
            cv2.putText(frame, "ALERT: YAWN DETECTED!", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
            y_offset += 40
            
        if snapshot["is_bad_posture"]:
            cv2.putText(frame, "ALERT: HEAD TILT ALERT!", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)

        return frame