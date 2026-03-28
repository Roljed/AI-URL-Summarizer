import sqlite3


def init_db():
    """Initializes a local SQLite database to cache agent outputs."""
    conn = sqlite3.connect("agent_memory.db")
    cursor = conn.cursor()
    # We store the URL as the unique key, and the strictly-typed JSON as the value
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summary_cache (
            url TEXT PRIMARY KEY,
            summary_json TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY,
            phone_number TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn


def get_cached_summary_json(conn: sqlite3.Connection, url: str) -> str | None:
    cursor = conn.cursor()
    cursor.execute("SELECT summary_json FROM summary_cache WHERE url = ?", (url,))
    row = cursor.fetchone()
    return row[0] if row else None


def save_summary_to_cache(conn: sqlite3.Connection, url: str, summary_json: str) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO summary_cache (url, summary_json) VALUES (?, ?)",
        (url, summary_json),
    )
    conn.commit()


def fetch_all_summary_json_rows(conn: sqlite3.Connection) -> list[tuple[str]]:
    cursor = conn.cursor()
    cursor.execute("SELECT summary_json FROM summary_cache")
    return cursor.fetchall()


def fetch_history_rows(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    cursor = conn.cursor()
    # We use SQLite's internal rowid to get chronological insertion order
    cursor.execute("SELECT url, summary_json FROM summary_cache ORDER BY rowid ASC")
    return cursor.fetchall()


def check_rate_limit(phone_number: str, max_requests: int = 10, hours: int = 12) -> bool:
    conn = sqlite3.connect("agent_memory.db")
    try:
        cursor = conn.cursor()
        modifier = f"-{hours} hours"
        cursor.execute(
            """
            SELECT COUNT(*) FROM usage_logs
            WHERE phone_number = ? AND timestamp >= datetime('now', ?)
            """,
            (phone_number, modifier),
        )
        row = cursor.fetchone()
        count = int(row[0]) if row else 0
        if count < max_requests:
            cursor.execute(
                "INSERT INTO usage_logs (phone_number) VALUES (?)",
                (phone_number,),
            )
            conn.commit()
            return True
        return False
    finally:
        conn.close()
