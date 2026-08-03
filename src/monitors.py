
import os
import math
import time
import queue
import pygame
import threading
from pynput import mouse, keyboard
from models import ActivitySnapshot, DetectionEvent




pygame.mixer.init()

# Get the folder where THIS script lives (d:\StudyGaurd\experiments)
script_dir = os.path.dirname(os.path.abspath(__file__))

# Go up one level (..) to StudyGaurd root, then into assets/alarms
reminder_path = os.path.join(script_dir, "..", "assets", "alarms", "reminder.wav")
aggressive_path = os.path.join(script_dir, "..", "assets", "alarms", "aggressive.wav")

# Load the sounds
reminder_sound = pygame.mixer.Sound(reminder_path)
aggressive_sound = pygame.mixer.Sound(aggressive_path)






class MouseMonitor:
    def __init__(self, parent):
        self.parent = parent
        self.last_x, self.last_y = None, None
        self.click_count, self.scroll_count, self.total_distance = 0, 0, 0
        self.listener = None

    def update_timestamp(self):
        if not self.parent.is_inactive: self.parent.last_active_time = time.monotonic()

    def on_move(self, x, y):
        if self.last_x is None and self.last_y is None:
            self.last_x, self.last_y = x, y
            return
        distance = math.sqrt((x - self.last_x)**2 + (y - self.last_y)**2)
        self.last_x, self.last_y = x, y
        self.total_distance += distance
        if self.parent.is_inactive:
            self.parent.accumulated_distance += distance
            if self.parent.accumulated_distance >= self.parent.active_distance_threshold:
                self.parent.wake_up(f"Mouse moved {self.parent.accumulated_distance:.1f}px")
        else:
            self.update_timestamp()

    def on_click(self, x, y, button, pressed):
        self.update_timestamp()
        if pressed:
            self.click_count += 1
            if self.parent.is_inactive:
                self.parent.accumulated_actions += 1
                if self.parent.accumulated_actions >= self.parent.active_click_threshold:
                    self.parent.wake_up(f"Clicked {self.parent.accumulated_actions} times")

    def on_scroll(self, x, y, dx, dy):
        self.update_timestamp()
        self.scroll_count += 1
        if self.parent.is_inactive:
            self.parent.accumulated_actions += 1
            if self.parent.accumulated_actions >= self.parent.active_click_threshold:
                self.parent.wake_up(f"Scrolled {self.parent.accumulated_actions} times")

    def start(self):
        self.listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        self.listener.start()

    def stop(self):
        if self.listener: self.listener.stop()




class KeyboardMonitor:
    def __init__(self, parent):
        self.parent = parent
        self.key_press_count = 0
        self.listener = None

    def update_timestamp(self):
        if not self.parent.is_inactive: self.parent.last_active_time = time.monotonic()

    def on_press(self, key):
        self.update_timestamp()
        self.key_press_count += 1
        if self.parent.is_inactive:
            self.parent.accumulated_actions += 1
            if self.parent.accumulated_actions >= self.parent.active_click_threshold:
                self.parent.wake_up(f"Typed {self.parent.accumulated_actions:} keys")

    def start(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def stop(self):
        if self.listener: self.listener.stop()







class CombinedActivityMonitor:
    def __init__(self, session_id: str, inactivity_threshold_seconds: int, base_distance: float, base_clicks: int, event_bus: queue):
        self.session_id = session_id
        
        self.event_bus = event_bus
        
        self.mouse = MouseMonitor(self)
        self.keyboard = KeyboardMonitor(self)
        
        self.inactive_threshold = inactivity_threshold_seconds
        
        self.base_distance = base_distance
        self.base_clicks = base_clicks
        self.active_distance_threshold = base_distance
        self.active_click_threshold = base_clicks
        self.alarm_level = 0 
        self.alarm_start_time = 0.0
        
        self.is_inactive = False
        self.activity_thread = None
        self.data_print_time = 5.0

        self.accumulated_distance = 0
        self.accumulated_actions = 0
        
        self.cooldown_end_time = 0.0
        
        self.last_active_time = time.monotonic()

    def get_latest_activity_time(self): return self.last_active_time

    def wake_up(self, reason):
        # 1. Stop any currently playing audio instantly
        pygame.mixer.stop()
        
        # 2. Log the dismissal event if an alarm was actually ringing
        if self.alarm_level > 0:
            self.event_bus.put(DetectionEvent(
                session_id=self.session_id,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                event_type="ALARM_DISMISSED",
                description=f"Awake via: {reason}"
            ))
            
        # 3. Reset states and remove the 25% penalty
        self.is_inactive = False
        self.alarm_level = 0
        self.cooldown_end_time = time.monotonic() + 60.0
        self.active_distance_threshold = self.base_distance
        self.active_click_threshold = self.base_clicks
        
        # 4. Reset movement counters
        self.accumulated_distance = 0
        self.unpause_click_count = 0
        self.unpause_scroll_count = 0
        self.unpause_key_count = 0
        self.last_active_time = time.monotonic()
        
        self.event_bus.put(DetectionEvent(
            session_id=self.session_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            event_type="ACTIVITY_RESUMED",
            description=reason
        ))

    def monitor_inactivity(self):
        while True:
            
            if time.monotonic() < self.cooldown_end_time:
                # Keep pushing the timestamp forward so the alarm doesn't instantly trigger when cooldown ends
                self.last_active_time = time.monotonic() 
                time.sleep(0.5)
                continue
            
            current_inactive_time = time.monotonic() - self.get_latest_activity_time()
            
            # LEVEL 1: The Nudge
            if current_inactive_time >= self.inactive_threshold and self.alarm_level == 0:
                self.is_inactive = True
                self.alarm_level = 1
                self.alarm_start_time = time.monotonic()
                
                # Play reminder on infinite loop (-1 means loop forever)
                reminder_sound.play(loops=-1)
                
                self.event_bus.put(DetectionEvent(
                    session_id=self.session_id,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    event_type="ALARM_STARTED",
                    description="Level 1 Nudge Started"
                ))

            # LEVEL 2: The Penalty (60 seconds later)
            elif self.alarm_level == 1 and (time.monotonic() - self.alarm_start_time) >= 60.0:
                self.alarm_level = 2
                
                # Stop the reminder sound first
                reminder_sound.stop()
                
                # Apply the 25% Penalty
                self.active_distance_threshold *= 1.25
                self.active_click_threshold = int(self.active_click_threshold * 1.25)
                
                # Play aggressive sound on infinite loop
                aggressive_sound.play(loops=-1)
                
                self.event_bus.put(DetectionEvent(
                    session_id=self.session_id,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    event_type="ALARM_ESCALATED",
                    description=f"Level 2 Penalty Applied. New Dist: {self.active_distance_threshold}, Clicks: {self.active_click_threshold}"
                ))

            time.sleep(0.5)

    def start(self):
        self.activity_thread = threading.Thread(target=self.monitor_inactivity, daemon=True)
        self.activity_thread.start()
        self.mouse.start()
        self.keyboard.start()

    def stop(self):
        self.mouse.stop()
        self.keyboard.stop()

    def get_snapshot(self):
        inactivity_seconds = time.monotonic() - self.get_latest_activity_time()
        snapshot = ActivitySnapshot(
            session_id=self.session_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            is_active=not self.is_inactive,
            mouse_distance_pixels=round(self.mouse.total_distance, 2),
            mouse_click_count=self.mouse.click_count,
            mouse_scroll_count=self.mouse.scroll_count,
            key_press_count=self.keyboard.key_press_count,
            inactivity_seconds=max(0.0, round(inactivity_seconds, 2)),
            inactivity_triggered=self.is_inactive
        )
        self.mouse.total_distance, self.mouse.click_count, self.mouse.scroll_count, self.keyboard.key_press_count = 0.0, 0, 0, 0
        return snapshot


