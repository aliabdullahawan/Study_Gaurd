
# Windows QuickEdit fix
if sys.platform == 'win32':
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 0x0080)




import time
import threading
from pynput import keyboard
import sys


class KeyboardMonitor:
    def __init__(self):
        self.last_active_time = time.monotonic()
        self.inactive_threshold = 5.0
        self.is_inactive = False
        
        self.listener = None
        self.activity_thread = None
        
        self.key_press_count = 0
        self.unpause_key_count = 0
        self.unpause_key_threshold = 5
        
        self.data_print_time = 5.0

    def wake_up(self, msg):
        print(msg)
        self.is_inactive = False
        self.unpause_key_count = 0
        self.last_active_time = time.monotonic()

    def update_timestamp(self):
        if not self.is_inactive:
            self.last_active_time = time.monotonic()

    def on_press(self, key):
        self.update_timestamp()
        self.key_press_count += 1
        
        if self.is_inactive:
            self.unpause_key_count += 1
            if self.unpause_key_count >= self.unpause_key_threshold:
                self.wake_up(f"\n[RESUMED] Typed {self.unpause_key_threshold} keys. Activity detected!")
        else:
            print(f"Key pressed... {key}")

    def monitor_inactivity(self):
        while True:
            current_time = time.monotonic() - self.last_active_time
            if current_time >= self.inactive_threshold and not self.is_inactive:
                print(f"\n[ALERT] User inactive! Type {self.unpause_key_threshold} keys to dismiss.")
                self.is_inactive = True
            time.sleep(0.5)

    def start(self):
        self.activity_thread = threading.Thread(target=self.monitor_inactivity, daemon=True)
        self.activity_thread.start()
        
        self.listener = keyboard.Listener(
            on_press=self.on_press
        )
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            self.listener.stop()

    def get_inactivity_seconds(self):
        return time.monotonic() - self.last_active_time

    def get_snapshot(self):
        snapshot = {
            "keyboard_active": not self.is_inactive,
            "key_press_count": self.key_press_count,
            "inactivity_seconds": round(self.get_inactivity_seconds(), 2),
            "inactivity_triggered": self.is_inactive
        }
        
        self.key_press_count = 0
        return snapshot

def main():
    monitor = KeyboardMonitor()

    print("Starting FocusGuard Keyboard Monitor...")
    print(f"Threshold set to {monitor.inactive_threshold} seconds.")
    print("Press Ctrl+C to stop.")

    monitor.start()

    try:
        while True:
            time.sleep(monitor.data_print_time)
            data = monitor.get_snapshot()
            print("\n----- 5 SECOND KEYBOARD SNAPSHOT -----")
            for key, val in data.items():
                print(f"{key} : {val}")
            print("--------------------------------------\n")
    except KeyboardInterrupt:
        print(f"\n\nKeyboard Detection Stopped.\n")
        monitor.stop()

if __name__ == "__main__":
    main()