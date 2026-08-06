import sys
import subprocess
from constants.path import MAIN

def main():
    # sys.executable ensures it uses your exact virtual environment Python automatically!
    try:
        subprocess.run([sys.executable, MAIN])
    except KeyboardInterrupt:
        # The child already handled the interrupt and saved everything.
        # Just pass silently so we don't see the ugly traceback.
        pass
print("[SYSTEM] Launcher exiting cleanly.")

if __name__ == "__main__":
    main()