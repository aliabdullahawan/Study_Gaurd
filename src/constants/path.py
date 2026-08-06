import os



## ALARM FILES PATH
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REMINDER_PATH = os.path.join(_SCRIPT_DIR,"..", "..", "assets", "alarms", "reminder.wav")
AGGRESSIVE_PATH = os.path.join(_SCRIPT_DIR,"..", "..", "assets", "alarms", "aggressive.wav")


## DATABASE FILE PATH
_DB_DIR = os.path.join(_SCRIPT_DIR,"..", "..", "assets", "database")
DB_FILE = os.path.join(_DB_DIR, "focusguard.db")
MAIN = os.path.join(_SCRIPT_DIR, "..", "main.py")


## FACE MARKER MODEL .task FILE PATH
FACE_LANDMARKER_PATH = os.path.join(_SCRIPT_DIR, "..", "..", "assets", "FaceLandMarks", "face_landmarker.task")


