"""Review and correct items that were saved as cultural works by mistake.

A social post is its own type (``post``). The application never infers that
type from the text or the HTML, and this migration does not infer it either:
it only reports suspicious rows and changes the explicit IDs a human confirms.

Usage::

    python migrate_posts.py                      # read-only report
    python migrate_posts.py --apply --ids 17     # change only item 17 to "post"
    python migrate_posts.py --rollback           # restore the previous types

The migration only changes ``items.type``. It never deletes rows and keeps a
backup of every changed row in ``item_type_migrations`` so it is reversible.
"""

import argparse
import sqlite3
from datetime import datetime, timezone

from app.database import DB_PATH
from app.item_types import CULTURAL_ITEM_TYPES, POST_TYPE

BACKUP_TABLE = "item_type_migrations"


def _connect(db_path=None):
    return sqlite3.connect(str(db_path or DB_PATH))


def _ensure_backup_table(conn):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (
            item_id INTEGER PRIMARY KEY,
            previous_type TEXT NOT NULL,
            new_type TEXT NOT NULL,
            migrated_at TEXT NOT NULL
        )
        """
    )


def _rows(conn, sql, params=()):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params)]


def report(db_path=None):
    """Return suspicious rows without modifying anything."""
    conn = _connect(db_path)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
            )
        ]
        if not tables:
            return {"candidates": [], "reason": "items table not found"}

        placeholders = ",".join("?" for _ in CULTURAL_ITEM_TYPES)
        rows = _rows(
            conn,
            f"""
            SELECT id, user_id, type, title, creator, pages, year,
                   thoughts, cover_url
            FROM items
            WHERE type IN ({placeholders})
              AND thoughts LIKE '%<%'
            ORDER BY id
            """,
            CULTURAL_ITEM_TYPES,
        )

        candidates = []
        for row in rows:
            candidates.append(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "current_type": row["type"],
                    "title": (row["title"] or "")[:80],
                    "creator": row["creator"],
                    "pages": row["pages"],
                    "year": row["year"],
                    "has_rich_text": "<" in (row["thoughts"] or ""),
                    "missing_work_metadata": not row["creator"] and not row["pages"],
                }
            )
        return {"candidates": candidates, "reason": "report only, nothing changed"}
    finally:
        conn.close()


def apply(ids, db_path=None):
    """Change the explicit item IDs to the ``post`` type, with a backup."""
    wanted = sorted({int(item_id) for item_id in ids})
    if not wanted:
        return {"changed": [], "skipped": [], "reason": "no ids provided"}

    conn = _connect(db_path)
    try:
        _ensure_backup_table(conn)
        changed = []
        skipped = []
        now = datetime.now(timezone.utc).isoformat()

        for item_id in wanted:
            row = _rows(
                conn, "SELECT id, type FROM items WHERE id = ?", (item_id,)
            )
            if not row:
                skipped.append({"id": item_id, "reason": "not found"})
                continue

            current_type = row[0]["type"]
            if current_type == POST_TYPE:
                skipped.append({"id": item_id, "reason": "already post"})
                continue
            if current_type not in CULTURAL_ITEM_TYPES:
                skipped.append(
                    {"id": item_id, "reason": f"unexpected type: {current_type}"}
                )
                continue

            conn.execute(
                f"""
                INSERT INTO {BACKUP_TABLE} (item_id, previous_type, new_type, migrated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    previous_type = excluded.previous_type,
                    new_type = excluded.new_type,
                    migrated_at = excluded.migrated_at
                """,
                (item_id, current_type, POST_TYPE, now),
            )
            conn.execute(
                "UPDATE items SET type = ? WHERE id = ?", (POST_TYPE, item_id)
            )
            changed.append({"id": item_id, "from": current_type, "to": POST_TYPE})

        conn.commit()
        return {"changed": changed, "skipped": skipped}
    finally:
        conn.close()


def rollback(db_path=None):
    """Restore every type recorded in the backup table."""
    conn = _connect(db_path)
    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (BACKUP_TABLE,),
        ).fetchone()
        if not has_table:
            return {"restored": [], "reason": "no backup table"}

        backups = _rows(
            conn,
            f"SELECT item_id, previous_type FROM {BACKUP_TABLE} ORDER BY item_id",
        )
        restored = []
        for backup in backups:
            conn.execute(
                "UPDATE items SET type = ? WHERE id = ?",
                (backup["previous_type"], backup["item_id"]),
            )
            conn.execute(
                f"DELETE FROM {BACKUP_TABLE} WHERE item_id = ?",
                (backup["item_id"],),
            )
            restored.append(
                {
                    "id": backup["item_id"],
                    "restored_type": backup["previous_type"],
                }
            )
        conn.commit()
        return {"restored": restored}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply the change")
    parser.add_argument(
        "--ids",
        type=int,
        nargs="+",
        help="explicit item IDs to change to type=post",
    )
    parser.add_argument(
        "--rollback", action="store_true", help="restore previous types"
    )
    parser.add_argument("--db", help="path to the SQLite database")
    args = parser.parse_args()

    if args.rollback:
        print(rollback(args.db))
    elif args.apply:
        if not args.ids:
            parser.error("--apply requires --ids")
        print("Changes to apply:")
        for item_id in args.ids:
            print(f"  item {item_id}: type -> {POST_TYPE}")
        print(apply(args.ids, args.db))
    else:
        print(report(args.db))


if __name__ == "__main__":
    main()
