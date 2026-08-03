

import os
import sqlite3




DB_FILE = "focusguard.db"

script_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Point to assets/database/ inside your project root
DB_DIR = os.path.join(script_dir, "..", "assets", "database")

# 4. Set the final path for your SQLite database file
DB_FILE = os.path.join(DB_DIR, "focusguard.db")



conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("SELECT * FROM metrics")
rows = cursor.fetchall()
for row in rows:
    print(f"Row pulled from SQLite: {row}")
conn.close()