import os
import time
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# Automatically find the model file relative to project root or experiments folder
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))



class FaceLandmarkEngine:
    def __init__(self):
        
        # Adjust path depending on where your file sits (e.g., if in src/focusguard/vision/ and model is in root)
        # Let's point to the model file safely:
        self.model_path = os.path.abspath(os.path.join(ROOT_DIR, "..", "..", "assets", "FaceLandMarks", "face_landmarker.task"))
        
        # Fallback check if model is in root or asset folder
        if not os.path.exists(self.model_path):
            # Try root folder path lookup
            self.model_path = os.path.abspath(os.path.join(ROOT_DIR, "..", "..", "face_landmarker.task"))

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Could not find 'face_landmarker.task' model file. Please place it in the project root or experiments folder.")

        # Configure MediaPipe Tasks
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        self.options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1
        )
        
        # with vision.FaceLandmarker.create_from_options(self.options) as landmarker:
        #     if not landmarker:
        #         raise MemoryError(f"Could not load and iniialize model into your memory.")
        self.landmarker = vision.FaceLandmarker.create_from_options(self.options)
        
        # Face missing tracking state
        self.last_face_seen_time = time.monotonic()
        self.is_face_present = False

    def process_frame(self, frame):
        """
        Processes a raw BGR OpenCV frame, runs MediaPipe FaceLandmarker,
        draws landmarks, and calculates face presence/missing duration.
        """
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        timestamp_ms = int(time.time() * 1000)

        # Run detection
        detection_result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

        current_time = time.monotonic()
        face_landmarks_list = None

        if detection_result.face_landmarks and len(detection_result.face_landmarks) > 0:
            face_landmarks_list = detection_result.face_landmarks[0]
            
            # Reset missing timer since face is present
            self.last_face_seen_time = current_time
            self.is_face_present = True
            
            # Draw landmarks onto the frame for visual confirmation
            for landmark in face_landmarks_list:
                x = int(landmark.x * frame.shape[1])
                y = int(landmark.y * frame.shape[0])
                cv2.circle(frame, (x, y), 1, (0, 0, 255), 0)
        else:
            self.is_face_present = False

        # Calculate how many seconds the face has been missing
        missing_duration = current_time - self.last_face_seen_time if not self.is_face_present else 0.0

        # Return structured analysis dictionary for the rest of the app to consume
        return {
            "face_detected": self.is_face_present,
            "face_missing_seconds": round(missing_duration, 2),
            "landmarks": face_landmarks_list,
            "annotated_frame": frame
        }

    def close(self):
        """Safely release MediaPipe resources."""
        if self.landmarker:
            self.landmarker.close()