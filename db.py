from pathlib import Path
import sqlite3
import pandas as pd

DB_PATH = Path("support_tickets.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(csv_path: str = "support_tickets.csv"):
    if DB_PATH.exists():
        return
    df = pd.read_csv(csv_path)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    df.to_sql("tickets", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_agent ON tickets(agent_id)")
    conn.commit()
    conn.close()

def query_df(sql: str, params: tuple = ()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df
