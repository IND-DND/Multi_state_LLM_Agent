import sqlite3

conn = sqlite3.connect('sales.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print('TABLES:', tables)
for table, in tables:
    print('\nSCHEMA for', table)
    cursor.execute(f"PRAGMA table_info({table})")
    for row in cursor.fetchall():
        print(row)

conn.close()
