import subprocess
import sys
import os

def main():
    # Automatically points to src/main.py
    script_path = os.path.join(os.path.dirname(__file__), "src", "main.py")
    
    # sys.executable ensures it uses your exact virtual environment Python automatically!
    subprocess.run([sys.executable, script_path])

if __name__ == "__main__":
    main()