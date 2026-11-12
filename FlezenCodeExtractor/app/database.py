import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from app.config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL,
                source_file TEXT,
                total_links INTEGER DEFAULT 0,
                status TEXT DEFAULT 'IN_PROGRESS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                serial_no INTEGER NOT NULL,
                url TEXT NOT NULL,
                code TEXT,
                confidence REAL DEFAULT 0.0,
                screenshot_filename TEXT,
                processing_status TEXT DEFAULT 'PENDING',
                verification_status TEXT DEFAULT 'UNVERIFIED',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_links_session ON links (session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_links_serial ON links (serial_no)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_links_status ON links (processing_status)")
    conn.close()

class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        init_db()

    def create_session(self, source_file: str, total_links: int, session_name: Optional[str] = None) -> int:
        if not session_name:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            session_name = f"Extraction Session - {now_str}"
        conn = get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sessions (session_name, source_file, total_links, status)
                VALUES (?, ?, ?, 'IN_PROGRESS')
            """, (session_name, source_file, total_links))
            session_id = cur.lastrowid
        conn.close()
        return session_id

    def get_latest_session(self) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def insert_links(self, session_id: int, links: List[Tuple[int, str]]):
        """Insert batch of (serial_no, url) pairs."""
        conn = get_connection()
        with conn:
            conn.executemany("""
                INSERT INTO links (session_id, serial_no, url, processing_status, verification_status)
                VALUES (?, ?, ?, 'PENDING', 'UNVERIFIED')
            """, [(session_id, serial, url) for serial, url in links])
        conn.close()

    def update_link_result(self, link_id: int, status: str, code: Optional[str] = None,
                           confidence: float = 0.0, screenshot_filename: Optional[str] = None,
                           verification_status: str = "UNVERIFIED", error_message: Optional[str] = None):
        conn = get_connection()
        with conn:
            conn.execute("""
                UPDATE links
                SET processing_status = ?,
                    code = ?,
                    confidence = ?,
                    screenshot_filename = COALESCE(?, screenshot_filename),
                    verification_status = ?,
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, code, confidence, screenshot_filename, verification_status, error_message, link_id))
        conn.close()

    def manual_update_code(self, link_id: int, new_code: str, verification_status: str = "EDITED"):
        conn = get_connection()
        with conn:
            conn.execute("""
                UPDATE links
                SET code = ?,
                    verification_status = ?,
                    processing_status = CASE WHEN processing_status = 'FAILED' THEN 'SUCCESS' ELSE processing_status END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_code.strip().upper(), verification_status, link_id))
        conn.close()

    def get_session_links(self, session_id: int, status_filter: Optional[str] = None,
                          search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection()
        query = "SELECT * FROM links WHERE session_id = ?"
        params: List[Any] = [session_id]

        if status_filter and status_filter.upper() != "ALL":
            if status_filter.upper() == "DUPLICATES":
                # Find links whose codes appear more than once in this session
                query += """ AND code IS NOT NULL AND code != '' AND code IN (
                    SELECT code FROM links WHERE session_id = ? AND code IS NOT NULL AND code != ''
                    GROUP BY code HAVING COUNT(*) > 1
                )"""
                params.append(session_id)
            else:
                query += " AND processing_status = ?"
                params.append(status_filter.upper())

        if search_query:
            q = f"%{search_query.strip()}%"
            query += " AND (code LIKE ? OR url LIKE ? OR CAST(serial_no AS TEXT) LIKE ?)"
            params.extend([q, q, q])

        query += " ORDER BY serial_no ASC"
        cur = conn.cursor()
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_session_metrics(self, session_id: int) -> Dict[str, int]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM links WHERE session_id = ?", (session_id,))
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM links WHERE session_id = ? AND processing_status != 'PENDING'", (session_id,))
        processed = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM links WHERE session_id = ? AND processing_status = 'SUCCESS'", (session_id,))
        successful = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM links WHERE session_id = ? AND processing_status = 'FAILED'", (session_id,))
        failed = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM links WHERE session_id = ? AND processing_status = 'NEEDS_REVIEW'", (session_id,))
        needs_review = cur.fetchone()[0]

        # Duplicate codes count
        cur.execute("""
            SELECT COUNT(*) FROM links WHERE session_id = ? AND code IS NOT NULL AND code != '' AND code IN (
                SELECT code FROM links WHERE session_id = ? AND code IS NOT NULL AND code != ''
                GROUP BY code HAVING COUNT(*) > 1
            )
        """, (session_id, session_id))
        duplicates = cur.fetchone()[0]

        conn.close()
        return {
            "total": total,
            "processed": processed,
            "successful": successful,
            "failed": failed,
            "needs_review": needs_review,
            "duplicates": duplicates
        }

    def reset_failed_links(self, session_id: int):
        conn = get_connection()
        with conn:
            conn.execute("""
                UPDATE links
                SET processing_status = 'PENDING',
                    error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ? AND processing_status IN ('FAILED', 'NEEDS_REVIEW')
            """, (session_id,))
        conn.close()

