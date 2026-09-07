import sqlite3
import pandas as pd

DB_PATH = "database/sales.db"

def execute_query(query):

    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query(query, conn)

    conn.close()

    return df