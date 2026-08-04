import cv2
import time


def test_camera():
    start_time = time.monotonic()
    print("[INFO] Opening webcam...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    camera_open_time = time.monotonic()
    if not cap.isOpened():
        print("[ERROR] Could not open webcam. Check permissions or connection.")
        return

    try:
        frame_count = 0
        
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Failed to grab frame.")
                break
                
            frame_count += 1
            
            # Show a simple preview window
            cv2.imshow("FocusGuard - Camera Test", frame)
            
            # Press 'q' to exit the test loop
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            # Throttle or measure FPS optionally
            time.sleep(0.03) # roughly ~30fps preview cap
            
    finally:
        cap.release()
        cv2.destroyAllWindows()
        end_time = time.monotonic()
        print("[INFO] Camera released successfully.")
        print(f"Total Frams: {frame_count}")
        print(f"Starting Time: {start_time}")
        print(f"Camera Starting Time: {camera_open_time}")
        print(f"Ending Time: {end_time}")
        print(f"Time difference between App starting and camera openning is : {camera_open_time - start_time}")
        print(f"App run for : {end_time - start_time}")

if __name__ == "__main__":
    test_camera()