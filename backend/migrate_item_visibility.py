"""Safe, idempotent migration that adds items.is_public.

Existing rows are kept and marked as public (1) so that content that was
already visible in the feed stays visible. No table, column or row is removed.
"""

import sqlite3

from app.database import DB_PATH


def migrate(db_path=None):
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(items)")]
        if not columns:
            # No items table yet: create_all will build it with the column.
            return {"path": path, "added": False, "reason": "items table not found"}

        if "is_public" in columns:
            return {"path": path, "added": False, "reason": "column already exists"}

        conn.execute(
            "ALTER TABLE items ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT 1"
        )
        conn.commit()
        return {"path": path, "added": True, "reason": "column added, existing rows public"}
    finally:
        conn.close()


if __name__ == "__main__":
    print(migrate())
