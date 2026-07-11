"""SQLite storage with FTS5 full-text search.

The database file (data/receipts.db) is the app's "local storage": one row per
receipt holding the extracted OCR text plus the path to the saved image. A FTS5
virtual table mirrors the text so searches like "IKEA" are fast and ranked.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path  TEXT NOT NULL,
    filename    TEXT NOT NULL,
    ocr_text    TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

-- external-content FTS index over the receipt text
CREATE VIRTUAL TABLE IF NOT EXISTS receipts_fts USING fts5(
    ocr_text,
    content='receipts',
    content_rowid='id'
);

-- keep the FTS index in sync with the receipts table
CREATE TRIGGER IF NOT EXISTS receipts_ai AFTER INSERT ON receipts BEGIN
    INSERT INTO receipts_fts(rowid, ocr_text) VALUES (new.id, new.ocr_text);
END;
CREATE TRIGGER IF NOT EXISTS receipts_ad AFTER DELETE ON receipts BEGIN
    INSERT INTO receipts_fts(receipts_fts, rowid, ocr_text)
    VALUES ('delete', old.id, old.ocr_text);
END;
CREATE TRIGGER IF NOT EXISTS receipts_au AFTER UPDATE ON receipts BEGIN
    INSERT INTO receipts_fts(receipts_fts, rowid, ocr_text)
    VALUES ('delete', old.id, old.ocr_text);
    INSERT INTO receipts_fts(rowid, ocr_text) VALUES (new.id, new.ocr_text);
END;
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the data folder, database, tables, FTS index and triggers."""
    ensure_dirs()
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def add_receipt(image_path: str, filename: str, ocr_text: str) -> int:
    """Insert a receipt and return its new id."""
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO receipts (image_path, filename, ocr_text, created_at) "
            "VALUES (?, ?, ?, ?)",
            (image_path, filename, ocr_text, created_at),
        )
        return int(cur.lastrowid)


def _fts_query(raw: str) -> str:
    """Turn a user's words into a safe FTS5 MATCH expression.

    Each whitespace-separated word is quoted (so punctuation can't break the
    query syntax) and given a trailing * for prefix matching, then AND-joined.
    """
    words = [w for w in raw.split() if w]
    if not words:
        return ""
    return " ".join(f'"{w.replace(chr(34), "")}"*' for w in words)


def search_receipts(query: str, limit: int = 100) -> list[dict]:
    """Full-text search. Returns matching receipts with a highlighted snippet."""
    match = _fts_query(query)
    if not match:
        return []
    sql = """
        SELECT r.id, r.filename, r.created_at,
               snippet(receipts_fts, 0, '[', ']', ' … ', 12) AS snippet
        FROM receipts_fts
        JOIN receipts r ON r.id = receipts_fts.rowid
        WHERE receipts_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    with get_connection() as conn:
        try:
            rows = conn.execute(sql, (match, limit)).fetchall()
        except sqlite3.OperationalError:
            # malformed FTS expression -> no results rather than a 500
            return []
    return [dict(row) for row in rows]


def list_receipts(limit: int = 100) -> list[dict]:
    """Most-recently-added receipts (used for the empty/browse state)."""
    sql = (
        "SELECT id, filename, created_at, "
        "substr(ocr_text, 1, 140) AS snippet "
        "FROM receipts ORDER BY id DESC LIMIT ?"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(row) for row in rows]


def get_receipt(receipt_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM receipts WHERE id = ?", (receipt_id,)
        ).fetchone()
    return dict(row) if row else None


def count_receipts() -> int:
    with get_connection() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0])
