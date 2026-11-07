"""Add ``comments.created_at`` safely and idempotently.

The column is nullable and additive: no row, table or existing value is
removed. Comments created before this column existed keep ``NULL`` because
their real timestamp is unknown and inventing one would falsify data.

Usage::

    python migrate_comments_created_at.py
"""

import argparse
import sqlite3

from app.database import DB_PATH

COLUMN = "created_at"


def migrate(db_path=None):
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(comments)")]
        if not columns:
            return {
                "path": path,
                "added": False,
                "reason": "comments table not found; create_all will build it",
            }
        if COLUMN in columns:
            return {"path": path, "added": False, "reason": "column already exists"}

        conn.execute(f"ALTER TABLE comments ADD COLUMN {COLUMN} DATETIME")
        conn.commit()
        return {
            "path": path,
            "added": True,
            "reason": "nullable column added; existing comments keep created_at NULL",
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="path to the SQLite database")
    args = parser.parse_args()
    print(migrate(args.db))


if __name__ == "__main__":
    main()
