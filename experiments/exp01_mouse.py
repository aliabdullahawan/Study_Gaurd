# Windows QuickEdit fix
import sys
if sys.platform == 'win32':
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 0x0080)



from pynput import mouse
import threading
import time
import math




class MouseMonitor:
    
    def __init__(self):
        self.last_active_time = time.monotonic()
        self.last_movement_print_time = 0
        self.inactive_threshold = 5.0
        self.move_print_threshold = 1.0
        self.is_inactive = False
        
        self.last_x = None
        self.last_y = None
        self.accumulated_distance = 0
        self.distance_threshold = 100
        
        self.listener = None
        self.activity_thread = None
        
        self.unpause_click_count = 0
        self.unpause_scroll_count = 0
        self.unpause_scroll_click_threshold = 5
        
        self.click_count = 0
        self.scroll_count = 0
        self.total_distance = 0
        self.move_event_count = 0
        
        self.data_print_time = 5
        
    
    def update_timestamp(self):
        if not self.is_inactive:
            self.last_active_time = time.monotonic()

    def monitor_inactivity(self):
        
        while True:
            current_time = time.monotonic() - self.last_active_time
            if current_time >= self.inactive_threshold and not self.is_inactive:
                print(f"\n[ALERT] User inactive! Move mouse {self.distance_threshold}px to dismiss.")
                self.is_inactive = True
            time.sleep(0.5)
    
    def start(self):
        
        self.activity_thread = threading.Thread(target= self.monitor_inactivity, daemon= True)
        self.activity_thread.start()
        
        self.listener = mouse.Listener(
            on_move= self.on_move,
            on_click= self.on_click,
            on_scroll= self.on_scroll
        )
        
        self.listener.start()
    
    def stop(self):
        if self.listener is not None:
            self.listener.stop()

    def wake_up(self, msg):
        print(msg)
        self.accumulated_distance = 0
        self.is_inactive = False
        self.unpause_click_count = 0
        self.unpause_scroll_count = 0
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
                msg = f"\n[RESUMED] Mouse moved {self.accumulated_distance:.1f}px. Activity detected!"
                self.wake_up(msg)
        else:
            self.update_timestamp()
            current_time = time.monotonic()
            if (current_time - self.last_movement_print_time) >= self.move_print_threshold:
                print(f"Mouse move at ({x} , {y})")
                self.last_movement_print_time = current_time

    def on_click(self, x, y, button, pressed):
        self.update_timestamp()
        if pressed:
            self.click_count += 1
            if self.is_inactive:
                self.unpause_click_count += 1
                if self.unpause_click_count >= self.unpause_scroll_click_threshold:
                    msg = f"\n[RESUMED] Mouse Clicked {self.unpause_click_count} times. Activity detected!"
                    self.wake_up(msg)
            else:
                print(f"{button} -> Pressed at ({x} , {y})")

    def on_scroll(self, x, y, dx, dy):
        self.update_timestamp()
        self.scroll_count += 1
        if self.is_inactive:
            self.unpause_scroll_count += 1
            if self.unpause_scroll_count >= self.unpause_scroll_click_threshold:
                msg = f"\n[RESUMED] Mouse Scrolled {self.unpause_scroll_count} times. Activity detected!"
                self.wake_up(msg)
        else:
            action = "Scroll up" if dy > 0 else "Scroll down"
            print(f"{action} at ({x} , {y})")
    
    def inactivity_seconds(self):
        return time.monotonic() - self.last_active_time

    def get_snapShot(self):
        snapShot = {
            "mouse_active": not self.is_inactive,
            "mouse_event_count": self.move_event_count,
            "mouse_distance_pixels": round(self.total_distance, 2),
            "mouse_click_count": self.click_count,
            "mouse_scroll_count": self.scroll_count,
            "inactivity_seconds": round(self.inactivity_seconds(), 2),
            "inactivity_triggered": self.is_inactive
        }
        self.move_event_count = 0
        self.click_count = 0
        self.scroll_count = 0
        self.total_distance = 0.0
        
        return snapShot
    






def main():
    
    monitor = MouseMonitor()

    print("Starting FocusGuard Inactivity Monitor...")
    print(f"Threshold set to {monitor.inactive_threshold} seconds.")
    print("Windows QuickEdit disabled: You can now click safely in the terminal!")
    print("Press Ctrl+C to stop.")

    monitor.start()

    try:
        while True:
            time.sleep(monitor.data_print_time)
            data = monitor.get_snapShot()
            print("\n----- 5 SECOND SNAPSHOT -----")
            for key, val in data.items():
                print(f"{key} : {val}")
            print("\n------------------------------\n\n")
    except KeyboardInterrupt:
        print(f"\n\nMovement Detection Stopped.\n\n")
        monitor.stop()

if __name__ == "__main__":
    main()