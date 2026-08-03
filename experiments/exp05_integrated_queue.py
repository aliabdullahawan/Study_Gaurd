import sys
if sys.platform == 'win32':
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 0x0080)

import time
import threading
import math
import queue
from dataclasses import dataclass
from pynput import mouse, keyboard

# --- The Dataclasses ---
@dataclass
class ActivitySnapshot:
    """A single object combining all metrics for a 5-second window."""
    timestamp: str
    is_active: bool
    mouse_distance_pixels: float
    mouse_click_count: int
    mouse_scroll_count: int
    key_press_count: int
    inactivity_seconds: float
    inactivity_triggered: bool

@dataclass
class DetectionEvent:
    """Records sudden, meaningful occurrences (like alerts)."""
    timestamp: str
    event_type: str
    description: str

# --- Thread-Safe Detection Event Bus ---
event_bus = queue.Queue()

# --- SENSOR 1: The Mouse ---
class MouseMonitor:
    def __init__(self, parent):
        self.parent = parent
        
        self.last_x = None
        self.last_y = None
        
        self.distance_threshold = 100
        self.unpause_threshold = 5
        
        self.click_count = 0
        self.scroll_count = 0
        self.total_distance = 0
        
        self.listener = None
        

    def update_timestamp(self):
        if not self.parent.is_inactive:
            self.parent.last_active_time = time.monotonic()

    def on_move(self, x, y):
        if self.last_x is None and self.last_y is None:
            self.last_x, self.last_y = x, y
            return
        
        distance = math.sqrt((x - self.last_x)**2 + (y - self.last_y)**2)
        self.last_x, self.last_y = x, y
        
        self.total_distance += distance
        
        if self.parent.is_inactive:
            self.parent.accumulated_distance += distance
            if self.parent.accumulated_distance >= self.distance_threshold:
                self.parent.wake_up(f"Mouse moved {self.parent.accumulated_distance:.1f}px")
        else:
            self.update_timestamp()

    def on_click(self, x, y, button, pressed):
        self.update_timestamp()
        if pressed:
            self.click_count += 1
            if self.parent.is_inactive:
                self.parent.unpause_click_count += 1
                if self.parent.unpause_click_count >= self.unpause_threshold:
                    self.parent.wake_up(f"Mouse clicked {self.parent.unpause_click_count} times")

    def on_scroll(self, x, y, dx, dy):
        self.update_timestamp()
        self.scroll_count += 1
        if self.parent.is_inactive:
            self.parent.unpause_scroll_count += 1
            if self.parent.unpause_scroll_count >= self.unpause_threshold:
                self.parent.wake_up(f"Mouse scrolled {self.parent.unpause_scroll_count} times")

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

# --- SENSOR 2: The Keyboard ---
class KeyboardMonitor:
    def __init__(self, parent):
        self.parent = parent
        
        self.key_press_count = 0
        self.unpause_key_threshold = 5
        
        self.listener = None
        

    def update_timestamp(self):
        if not self.parent.is_inactive:
            self.parent.last_active_time = time.monotonic()

    def on_press(self, key):
        self.update_timestamp()
        self.key_press_count += 1
        
        if self.parent.is_inactive:
            self.parent.unpause_key_count += 1
            if self.parent.unpause_key_count >= self.unpause_key_threshold:
                self.parent.wake_up(f"Typed {self.unpause_key_threshold} keys")

    def start(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            self.listener.stop()

# --- MANAGER: Combined Activity Monitor ---
class CombinedActivityMonitor:
    def __init__(self):
        self.mouse = MouseMonitor(self)
        self.keyboard = KeyboardMonitor(self)
        
        self.inactive_threshold = 5.0
        self.is_inactive = False
        self.activity_thread = None
        self.data_print_time = 3.0

        self.accumulated_distance = 0
        self.unpause_click_count = 0
        self.unpause_scroll_count = 0
        self.unpause_key_count = 0
        
        self.last_active_time = time.monotonic()

    def get_latest_activity_time(self):
        return self.last_active_time

    def wake_up(self, reason):
        self.is_inactive = False

        self.accumulated_distance = 0
        self.unpause_click_count = 0
        self.unpause_scroll_count = 0
        self.unpause_key_count = 0
        
        self.last_active_time = time.monotonic()
        
        # Drop an Event into the queue when the user wakes up
        resume_event = DetectionEvent(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            event_type="ACTIVITY_RESUMED",
            description=reason
        )
        event_bus.put(resume_event)

    def monitor_inactivity(self):
        while True:
            current_time = time.monotonic() - self.get_latest_activity_time()
            
            if current_time >= self.inactive_threshold and not self.is_inactive:
                self.is_inactive = True
                
                # Drop an Event into the queue when inactivity triggers
                alert_event = DetectionEvent(
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    event_type="INACTIVITY_ALERT",
                    description=f"User inactive for {self.inactive_threshold} seconds."
                )
                event_bus.put(alert_event)
                
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
        self.keyboard.key_press_count = 0
        
        return snapshot

# --- THE CONSUMER THREAD ---
def process_queue_data():
    """Runs continuously in the background, simulating a database writer."""
    print("[CONSUMER] Database processor thread started, waiting for data...")
    while True:
        data_item = event_bus.get() 
        
        if isinstance(data_item, DetectionEvent):
            print(f"\n>>> [DATABASE] SAVED EVENT: {data_item.event_type} | {data_item.description}")
        elif isinstance(data_item, ActivitySnapshot):
            print(f"\n>>> [DATABASE] SAVED SNAPSHOT | Active: {data_item.is_active} | MousePx: {data_item.mouse_distance_pixels} | Keys: {data_item.key_press_count}")
            
        event_bus.task_done()



def main():
    # 1. Start the Consumer
    consumer_thread = threading.Thread(target=process_queue_data, daemon=True)
    consumer_thread.start()

    # 2. Start the Sensors
    monitor = CombinedActivityMonitor()
    print("Starting FocusGuard EVENT BUS Architecture...")
    print("Press Ctrl+C to stop.")
    monitor.start()

    # 3. Main Loop (Producer for Snapshots)
    try:
        while True:
            time.sleep(monitor.data_print_time)
            # Fetch the snapshot and push it to the queue instead of printing directly
            data = monitor.get_snapshot()
            event_bus.put(data)
            
    except KeyboardInterrupt:
        print(f"\n\n[SYSTEM] Ctrl+C Detected. Initiating graceful shutdown...")
        monitor.stop()
        
        print("[SYSTEM] Waiting for remaining queue data to save...")
        event_bus.join() # Prevents data loss on exit! (ctrl+c only not foced close included)
        print("[SYSTEM] All data saved. Program closed safely.")

if __name__ == "__main__":
    main()