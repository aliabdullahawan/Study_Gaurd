import sys
if sys.platform == 'win32':
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 0x0080)

import time
import threading
import math
from dataclasses import dataclass
from pynput import mouse, keyboard


@dataclass
class ActivitySnapshot:
    timestamp: str
    is_active: bool
    mouse_distance_pixels: float
    mouse_click_count: int
    mouse_scroll_count: int
    key_press_count: int
    inactivity_seconds: float
    inactivity_triggered: bool

class MouseMonitor:
    def __init__(self, wake_callback):
        self.last_active_time = time.monotonic()
        self.is_inactive = False
        self.wake_callback = wake_callback
        
        self.last_x = None
        self.last_y = None
        
        self.accumulated_distance = 0
        self.distance_threshold = 100
        self.unpause_click_count = 0
        self.unpause_scroll_count = 0
        self.unpause_threshold = 5
        
        self.click_count = 0
        self.scroll_count = 0
        self.total_distance = 0
        self.move_event_count = 0
        
        self.listener = None

    def update_timestamp(self):
        if not self.is_inactive:
            self.last_active_time = time.monotonic()

    def on_move(self, x, y):
        if self.last_x is None and self.last_y is None:
            self.last_x, self.last_y = x, y
            return
        
        distance = math.sqrt((x - self.last_x)**2 + (y - self.last_y)**2)
        self.last_x, self.last_y = x, y
        
        self.total_distance += distance
        self.move_event_count += 1
        
        if self.is_inactive:
            self.accumulated_distance += distance
            if self.accumulated_distance >= self.distance_threshold:
                self.wake_callback(f"Mouse moved {self.accumulated_distance:.1f}px")
        else:
            self.update_timestamp()

    def on_click(self, x, y, button, pressed):
        self.update_timestamp()
        if pressed:
            self.click_count += 1
            if self.is_inactive:
                self.unpause_click_count += 1
                if self.unpause_click_count >= self.unpause_threshold:
                    self.wake_callback(f"Mouse clicked {self.unpause_click_count} times")

    def on_scroll(self, x, y, dx, dy):
        self.update_timestamp()
        self.scroll_count += 1
        if self.is_inactive:
            self.unpause_scroll_count += 1
            if self.unpause_scroll_count >= self.unpause_threshold:
                self.wake_callback(f"Mouse scrolled {self.unpause_scroll_count} times")

    def start(self):
        self.listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click, 
            on_scroll=self.on_scroll
        )
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            self.listener.stop()

class KeyboardMonitor:
    def __init__(self, wake_callback):
        self.last_active_time = time.monotonic()
        self.is_inactive = False
        self.wake_callback = wake_callback
        
        self.key_press_count = 0
        self.unpause_key_count = 0
        self.unpause_key_threshold = 5
        
        self.listener = None

    def update_timestamp(self):
        if not self.is_inactive:
            self.last_active_time = time.monotonic()

    def on_press(self, key):
        self.update_timestamp()
        self.key_press_count += 1
        
        if self.is_inactive:
            self.unpause_key_count += 1
            if self.unpause_key_count >= self.unpause_key_threshold:
                self.wake_callback(f"Typed {self.unpause_key_threshold} keys")

    def start(self):
        self.listener = keyboard.Listener(
            on_press=self.on_press
        )
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            self.listener.stop()


class CombinedActivityMonitor:
    def __init__(self):
        
        self.mouse = MouseMonitor(wake_callback=self.wake_up)
        self.keyboard = KeyboardMonitor(wake_callback=self.wake_up)
        
        self.inactive_threshold = 5.0
        self.is_inactive = False
        self.activity_thread = None
        self.data_print_time = 5.0

    def get_latest_activity_time(self):
        
        return max(self.mouse.last_active_time, self.keyboard.last_active_time)

    def wake_up(self, reason):
        
        print(f"\n[RESUMED] {reason}. Combined activity detected!")
        self.is_inactive = False
        
        self.mouse.is_inactive = False
        self.keyboard.is_inactive = False

        self.mouse.accumulated_distance = 0
        self.mouse.unpause_click_count = 0
        self.mouse.unpause_scroll_count = 0
        self.keyboard.unpause_key_count = 0
        
        self.mouse.last_active_time = time.monotonic()
        self.keyboard.last_active_time = time.monotonic()

    def monitor_inactivity(self):
        while True:
            current_time = time.monotonic() - self.get_latest_activity_time()
            
            if current_time >= self.inactive_threshold and not self.is_inactive:
                print(f"\n[ALERT] User inactive! Move mouse 100px, click/scroll 5 times, or type 5 keys to dismiss.")
                self.is_inactive = True
                
                self.mouse.is_inactive = True
                self.keyboard.is_inactive = True
                
            time.sleep(0.5)

    def start(self):
        self.activity_thread = threading.Thread(
            target=self.monitor_inactivity, daemon=True
        )
        self.activity_thread.start()
        
        self.mouse.start()
        self.keyboard.start()

    def stop(self):
        self.mouse.stop()
        self.keyboard.stop()

    def get_snapshot(self):
        
        inactivity_seconds = time.monotonic() - self.get_latest_activity_time()
        
        snapshot = ActivitySnapshot(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            is_active=not self.is_inactive,
            mouse_distance_pixels=round(self.mouse.total_distance, 2),
            mouse_click_count=self.mouse.click_count,
            mouse_scroll_count=self.mouse.scroll_count,
            key_press_count=self.keyboard.key_press_count,
            inactivity_seconds=max(0.0, round(inactivity_seconds, 2)),
            inactivity_triggered=self.is_inactive
        )
        
        self.mouse.total_distance = 0.0
        self.mouse.click_count = 0
        self.mouse.scroll_count = 0
        self.mouse.move_event_count = 0
        self.keyboard.key_press_count = 0
        
        return snapshot

# --- EXECUTION ---
def main():
    monitor = CombinedActivityMonitor()

    print("Starting FocusGuard COMBINED Monitor...")
    print(f"Threshold set to {monitor.inactive_threshold} seconds.")
    print("Press Ctrl+C to stop.")

    monitor.start()

    try:
        while True:
            time.sleep(monitor.data_print_time)
            data = monitor.get_snapshot()
            
            print("\n----- 5 SECOND UNIFIED SNAPSHOT -----")
            for key, val in data.__dict__.items():
                print(f"{key} : {val}")
            print("--------------------------------------\n")
            
    except KeyboardInterrupt:
        print(f"\n\nCombined Detection Stopped.\n")
        monitor.stop()

if __name__ == "__main__":
    main()