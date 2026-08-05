import os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REMINDER_PATH = os.path.join(_SCRIPT_DIR,"..", "..", "assets", "alarms", "reminder.wav")
AGGRESSIVE_PATH = os.path.join(_SCRIPT_DIR,"..", "..", "assets", "alarms", "aggressive.wav")

_DB_DIR = os.path.join(_SCRIPT_DIR,"..", "..", "assets", "database")
DB_FILE = os.path.join(_DB_DIR, "focusguard.db")
MAIN = os.path.join(_SCRIPT_DIR, "..", "main.py")