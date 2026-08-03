import sqlite3
DB_FILE = "focusguard.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("SELECT * FROM metrics")
rows = cursor.fetchall()
for row in rows:
    print(f"Row pulled from SQLite: {row}")
conn.close()