"""Create the friendships and notifications tables safely and idempotently.

The migration is purely additive: it never drops or alters existing tables,
columns or rows. Running it twice has no effect.

It also guarantees the canonical unique index that makes a user pair unique in
both directions:

    UNIQUE INDEX (min(requester_id, addressee_id), max(requester_id, addressee_id))

That index is what stops ``A -> B`` and ``B -> A`` from coexisting when two
requests are processed concurrently. If legacy duplicate pairs are found, the
migration reports them and refuses to create the index instead of deleting data.

Usage::

    python migrate_friends_notifications.py
"""

import argparse
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app import models  # noqa: F401 - register every model on Base.metadata
from app.database import Base, DB_PATH

TABLES = ("friendships", "notifications")
CANONICAL_INDEX = "uq_friendship_canonical_pair"
CANONICAL_INDEX_SQL = (
    f"CREATE UNIQUE INDEX IF NOT EXISTS {CANONICAL_INDEX} "
    "ON friendships (min(requester_id, addressee_id), max(requester_id, addressee_id))"
)


def _duplicate_pairs(connection):
    rows = connection.exec_driver_sql(
        "SELECT min(requester_id, addressee_id) AS low, "
        "max(requester_id, addressee_id) AS high, COUNT(*) AS total "
        "FROM friendships GROUP BY low, high HAVING total > 1"
    ).fetchall()
    return [tuple(row) for row in rows]


def migrate(db_path=None):
    path = Path(db_path or DB_PATH)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        existing = set(inspect(engine).get_table_names())
        Base.metadata.create_all(bind=engine)
        created = [table for table in TABLES if table not in existing]

        with engine.begin() as connection:
            index_names = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                )
            }
            index_created = False
            if CANONICAL_INDEX not in index_names:
                duplicates = _duplicate_pairs(connection)
                if duplicates:
                    raise RuntimeError(
                        "No se creó el índice único: existen pares de amistad "
                        f"duplicados que requieren revisión manual: {duplicates}"
                    )
                connection.exec_driver_sql(CANONICAL_INDEX_SQL)
                index_created = True

        return {
            "path": str(path),
            "created": created,
            "canonical_index_created": index_created,
            "reason": (
                "additive tables and/or unique index created"
                if created or index_created
                else "tables and unique index already exist; nothing to do"
            ),
        }
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="path to the SQLite database")
    args = parser.parse_args()
    print(migrate(args.db))


if __name__ == "__main__":
    main()
