import os
import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision




# 1. Get the folder where THIS script is currently living (experiments/)
script_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Build a bulletproof absolute path to the task file
model_path = os.path.join(script_dir, "face_landmarker.task")



def run_face_landmarker():
    print("[INFO] Starting camera and loading MediaPipe FaceLandmarker...")
    
    # 1. Open the webcam using DirectShow (fixes Windows 30-second lag)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    # 2. Configure the modern MediaPipe Tasks settings
    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO, # Tells MediaPipe this is a live video stream
        num_faces=1                           # We only want to track 1 student at a time
    )

    # 3. Create the landmarker tool using a context manager
    print("[INFO] Loading AI Face Model into memory (this may take a few seconds)...")
    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        print("[INFO] Model loaded! Launching camera...")
        try:
            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    print("[WARNING] Failed to grab camera frame.")
                    break

                # OpenCV reads frames as BGR (Blue-Green-Red). 
                # MediaPipe expects RGB (Red-Green-Blue). We convert it here:
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Wrap the frame into MediaPipe's custom image format
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                
                # Generate a millisecond timestamp (required for video mode)
                timestamp_ms = int(time.time() * 1000)
                
                # Run the AI detection on this specific frame
                detection_result = landmarker.detect_for_video(mp_image, timestamp_ms)

                # If a face is found, draw a tiny green dot on every landmark coordinate
                if detection_result.face_landmarks:
                    for face_landmarks in detection_result.face_landmarks:
                        for landmark in face_landmarks:
                            # Convert normalized 0.0-1.0 coordinates into actual pixel screen coordinates
                            x = int(landmark.x * frame.shape[1])
                            y = int(landmark.y * frame.shape[0])
                            # Draw a small green dot (radius 1, green color, filled)
                            cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

                # Show the video feed on your screen
                cv2.imshow("FocusGuard - Face Landmarker Test", frame)

                # Press 'q' on your keyboard while clicking the video window to quit
                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
                    
        finally:
            # Always clean up hardware and windows when done
            cap.release()
            cv2.destroyAllWindows()
            print("[INFO] Camera closed and test ended successfully.")

if __name__ == "__main__":
    run_face_landmarker()