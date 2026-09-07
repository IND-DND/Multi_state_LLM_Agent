import sqlite3
from pathlib import Path

base_dir = Path(__file__).resolve().parent
schema_file = base_dir / "schema.sql"

db_file = base_dir / "sales.db"
conn = sqlite3.connect(db_file)

cursor = conn.cursor()

with schema_file.open("r") as file:
    cursor.executescript(file.read())

conn.commit()
conn.close()

print("Database Created")