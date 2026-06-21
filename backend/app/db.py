import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # 서버-스크립트 동시 접근 허용
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def migrate_db():
    """기존 DB에 신규 컬럼을 안전하게 추가한다."""
    with get_conn() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(headlines)").fetchall()}
        if "preprocessed_headline" not in cols:
            conn.execute("ALTER TABLE headlines ADD COLUMN preprocessed_headline TEXT")
            print("[migrate] headlines.preprocessed_headline 컬럼 추가됨")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS headlines (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                headline             TEXT    NOT NULL,
                preprocessed_headline TEXT,
                category             TEXT    NOT NULL,
                publisher            TEXT    NOT NULL,
                published_at         TEXT    NOT NULL,
                url                  TEXT    NOT NULL UNIQUE,
                collected_at         TEXT    DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS emotion_results (
                headline_id     INTEGER PRIMARY KEY REFERENCES headlines(id),
                emotion_probs   TEXT NOT NULL,
                attention_weights TEXT,
                predicted_at    TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS crawler_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            INSERT OR IGNORE INTO crawler_meta (key, value) VALUES ('last_crawled_at', NULL);
        """)
