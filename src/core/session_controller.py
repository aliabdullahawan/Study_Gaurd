import cv2
import time
import queue
import sqlite3
import threading
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from constants.path import DB_FILE, FACE_LANDMARKER_PATH
from core.session_manager import SessionManager
from model.detection_event import DetectionEvent
from model.activity_snapshot import ActivitySnapshot
from monitor.monitors import CombinedActivityMonitor
from monitor.fatigue_engine import FatigueDecisionEngine
from vision.vision_engine import VisionEngine

class SessionController:
    def __init__(self, user_baseline, config):
        """
        config should be a dictionary containing:
        session_mins, alarm_mins, base_distance, base_clicks
        """
        self.baseline = user_baseline
        self.config = config
        
        # Extract cooldown from config dictionary
        self.cooldown_sec = config.get('alarm_cooldown_sec', 60.0)
        
        # Core Systems
        self.session_manager = SessionManager()
        self.vision_engine = VisionEngine(self.baseline)
        self.fatigue_engine = FatigueDecisionEngine()
        
        # Threading & Data
        self.event_bus = queue.Queue()
        self.is_running = False
        self.active_session = None
        self.monitor = None
        
    def start_session(self, ui_callback=None):
        """Starts all threads, cameras, and hardware trackers."""
        if self.is_running: return
        self.is_running = True
        
        planned_duration_sec = int(self.config['session_mins'] * 60)
        inactivity_threshold_sec = int(self.config['alarm_mins'] * 60)

        # 1. Start Database Worker Thread
        threading.Thread(target=self._process_queue_data, daemon=True).start()

        # 2. Start Session in DB
        self.active_session = self.session_manager.start_session(
            planned_duration_sec=planned_duration_sec,
            inactivity_threshold_sec=inactivity_threshold_sec
        )

        # 3. Start Hardware Monitor
        self.monitor = CombinedActivityMonitor(
            session_id=self.active_session.session_id, 
            inactivity_threshold_seconds=inactivity_threshold_sec,
            base_distance=self.config['base_distance'],    
            base_clicks=self.config['base_clicks'],
            cooldown_sec=self.cooldown_sec,
            event_bus=self.event_bus
        )
        self.monitor.start()

        # 4. Start the Camera/AI Loop in the background!
        threading.Thread(
            target=self._core_loop, 
            args=(ui_callback,), 
            daemon=True
        ).start()

    def stop_session(self, reason="MANUAL_STOP"):
        """Safely shuts down everything."""
        self.is_running = False
        if self.monitor:
            # Final data flush before stopping
            final_data = self.monitor.get_snapshot()
            self.event_bus.put(final_data)
            self.monitor.stop()
            
        if self.active_session:
            self.session_manager.end_session(reason=reason)
            
        print("[SYSTEM] Waiting for remaining data to save to database...")
        self.event_bus.join()
        print("[SYSTEM] All data successfully saved.")

    # def _core_loop(self, ui_callback):
    #     """This replaces your old while True loop. It runs the camera and the timer."""
    #     options = vision.FaceLandmarkerOptions(
    #         base_options=python.BaseOptions(model_asset_path=FACE_LANDMARKER_PATH),
    #         running_mode=vision.RunningMode.VIDEO,
    #         num_faces=1
    #     )
    #     cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    #     app_start = time.monotonic()
        
    #     last_eval_time = time.time()
    #     last_snapshot_time = time.monotonic()

    #     with vision.FaceLandmarker.create_from_options(options) as landmarker:
    #         while cap.isOpened() and self.is_running:
    #             current_time = time.monotonic()
                
    #             # --- 1. AUTO-KILL CHECK ---
    #             if self.active_session.get_duration_seconds() >= self.active_session.planned_duration_seconds:
    #                 print("\n[SYSTEM] Planned study duration reached!")
    #                 self.stop_session(reason="AUTO_COMPLETE")
    #                 break

    #             # --- 2. VISION PROCESSING ---
    #             success, frame = cap.read()
    #             if not success: continue

    #             h, w, _ = frame.shape
    #             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    #             mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    #             timestamp_ms = int((current_time - app_start) * 1000)

    #             results = landmarker.detect_for_video(mp_image, timestamp_ms)
    #             vision_snapshot = None
                
    #             if results.face_landmarks:
    #                 landmarks = results.face_landmarks[0]
    #                 vision_snapshot = self.vision_engine.process_landmarks(landmarks, w, h, current_time)
    #                 frame = self.vision_engine.draw_debug_visuals(frame, vision_snapshot)

    #             # --- 3. FATIGUE ENGINE (Runs every 1 second) ---
    #             current_clock = time.time()
    #             if vision_snapshot and (current_clock - last_eval_time) >= 1.0:
    #                 mouse_active = not self.monitor.is_inactive
    #                 key_active = not self.monitor.is_inactive # Simplified for now
    #                 report = self.fatigue_engine.evaluate_state(vision_snapshot, mouse_active, key_active)
    #                 last_eval_time = current_clock
                    
    #                 # Update UI if provided
    #                 if ui_callback:
    #                     ui_callback(report, frame)

    #             # --- 4. DATABASE SNAPSHOT (Runs every 5 seconds) ---
    #             if current_time - last_snapshot_time >= self.monitor.data_print_time:
    #                 # Get hardware snapshot
    #                 data = self.monitor.get_snapshot()
                    
    #                 # INJECT VISION DATA!
    #                 # INJECT VISION DATA!
    #                 if vision_snapshot:
    #                     data.ear = vision_snapshot.get("ear", 0.0)
    #                     data.mar = vision_snapshot.get("mar", 0.0)
    #                     data.pitch = vision_snapshot.get("pitch", 0.0)
    #                     data.yaw = vision_snapshot.get("yaw", 0.0)
    #                     data.roll = vision_snapshot.get("roll", 0.0)

                        
    #                 # INJECT FATIGUE DATA!
    #                 data.fatigue_score = self.fatigue_engine.fatigue_score
    #                 data.fatigue_state = self.fatigue_engine.current_state.value
                    
    #                 self.event_bus.put(data)
    #                 last_snapshot_time = current_time

    #     cap.release()
    
    
    
    
    def _core_loop(self, ui_callback):
        """Runs the camera feed at 30 FPS, evaluates fatigue, and auto-dismisses alarms when eyes are open."""
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=FACE_LANDMARKER_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1
        )
        
        # Initialize camera with explicit 30 FPS and smooth resolution
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        app_start = time.monotonic()
        last_eval_time = time.time()
        last_snapshot_time = time.monotonic()

        with vision.FaceLandmarker.create_from_options(options) as landmarker:
            while cap.isOpened() and self.is_running:
                current_time = time.monotonic()
                
                # --- 1. AUTO-KILL CHECK ---
                if self.active_session.get_duration_seconds() >= self.active_session.planned_duration_seconds:
                    print("\n[SYSTEM] Planned study duration reached!")
                    self.stop_session(reason="AUTO_COMPLETE")
                    break

                # --- 2. VISION PROCESSING ---
                success, frame = cap.read()
                if not success: 
                    continue

                h, w, _ = frame.shape
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                timestamp_ms = int((current_time - app_start) * 1000)

                results = landmarker.detect_for_video(mp_image, timestamp_ms)
                vision_snapshot = None
                
                if results.face_landmarks:
                    landmarks = results.face_landmarks[0]
                    vision_snapshot = self.vision_engine.process_landmarks(landmarks, w, h, current_time)
                    frame = self.vision_engine.draw_debug_visuals(frame, vision_snapshot)

                    # --- SMART OVERRIDE & AUTO-DISMISS ALARM ---
                    if self.monitor:
                        # If eyes are open (not in prolonged closure), user is awake!
                        if not vision_snapshot.get("is_prolonged_closure", False):
                            # Refresh activity so inactivity timer doesn't trip
                            self.monitor.refresh_activity()
                            
                            # If an alarm was ringing, KILL THE ALARM IMMEDIATELY
                            if self.monitor.is_inactive or self.monitor.alarm_level > 0:
                                self.monitor.wake_up("Eyes open detected - turning off alarm!")

                # --- 3. FATIGUE ENGINE (Runs every 1 second) ---
                current_clock = time.time()
                if vision_snapshot and (current_clock - last_eval_time) >= 1.0:
                    mouse_active = not self.monitor.is_inactive
                    key_active = not self.monitor.is_inactive 
                    report = self.fatigue_engine.evaluate_state(vision_snapshot, mouse_active, key_active)
                    last_eval_time = current_clock
                    
                    # Play alarm if critical threshold (100) is reached by eye closure or head tilt
                    if report.get('trigger_alarm', False):
                        if self.monitor and self.monitor.alarm_level == 0:
                            self.monitor.alarm_level = 1
                            if self.monitor.reminder_sound:
                                self.monitor.reminder_sound.play(loops=-1)
                    
                    # Stop alarm automatically when user straightens head / opens eyes (returns to NORMAL)
                    if report.get('state') == 'NORMAL' and self.monitor and self.monitor.alarm_level > 0:
                        self.monitor.wake_up("Vision fatigue condition resolved")
                    
                    if ui_callback:
                        ui_callback(report, frame)

                # --- 4. DATABASE SNAPSHOT (Runs every 5 seconds) ---
                if current_time - last_snapshot_time >= self.monitor.data_print_time:
                    data = self.monitor.get_snapshot()
                    
                    if vision_snapshot:
                        data.ear = vision_snapshot.get("ear", 0.0)
                        data.mar = vision_snapshot.get("mar", 0.0)
                        data.pitch = vision_snapshot.get("pitch", 0.0)
                        data.yaw = vision_snapshot.get("yaw", 0.0)
                        data.roll = vision_snapshot.get("roll", 0.0)
                        
                    data.fatigue_score = self.fatigue_engine.fatigue_score
                    data.fatigue_state = self.fatigue_engine.current_state.value
                    
                    self.event_bus.put(data)
                    last_snapshot_time = current_time

        cap.release()

    def _process_queue_data(self):
        """Your exact database worker, updated with the new columns!"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        while self.is_running or not self.event_bus.empty():
            try:
                data_item = self.event_bus.get(timeout=1.0) 
            except queue.Empty:
                continue

            if isinstance(data_item, DetectionEvent):
                cursor.execute("""
                    INSERT INTO events (session_id, timestamp, event_type, description)
                    VALUES (?, ?, ?, ?)
                """, (data_item.session_id, data_item.timestamp, data_item.event_type, data_item.description))
                
            elif isinstance(data_item, ActivitySnapshot):
                cursor.execute("""
                    INSERT INTO metrics (
                        session_id, timestamp, is_active, mouse_distance_pixels, 
                        mouse_click_count, mouse_scroll_count, key_press_count, 
                        inactivity_seconds, inactivity_triggered,
                        ear, mar, pitch, yaw, roll,
                        total_blinks, total_yawns, total_posture_warnings, fatigue_score, fatigue_state
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data_item.session_id, data_item.timestamp, data_item.is_active, 
                    data_item.mouse_distance_pixels, data_item.mouse_click_count, 
                    data_item.mouse_scroll_count, data_item.key_press_count, 
                    data_item.inactivity_seconds, data_item.inactivity_triggered,
                    data_item.ear, data_item.mar, data_item.pitch, data_item.yaw, data_item.roll,
                    data_item.total_blinks, data_item.total_yawns, data_item.total_posture_warnings,
                    data_item.fatigue_score, data_item.fatigue_state
                ))
                
            conn.commit()
            self.event_bus.task_done()