"""Add password-reset support without deleting or rewriting data.

Changes are purely additive and idempotent:

* ``users.token_version`` (INTEGER NOT NULL DEFAULT 0) lets a reset invalidate
  every JWT minted before the password change.
* ``password_reset_tokens`` stores only SHA-256 hashes of single-use tokens.

Usage::

    python migrate_password_reset.py
"""

import argparse
import sqlite3

from app.database import DB_PATH


TABLE_DDL = """
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME,
    created_at DATETIME NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users (id)
)
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_id "
    "ON password_reset_tokens (id)",
    "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id "
    "ON password_reset_tokens (user_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_tokens_token_hash "
    "ON password_reset_tokens (token_hash)",
)


def migrate(db_path=None):
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    try:
        result = {
            "path": path,
            "token_version_added": False,
            "table_created": False,
            "reason": "",
        }

        user_columns = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
        if not user_columns:
            result["reason"] = "users table not found; create_all will build the schema"
            return result

        if "token_version" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"
            )
            result["token_version_added"] = True

        existed = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='password_reset_tokens'"
        ).fetchone()
        conn.execute(TABLE_DDL)
        for statement in INDEXES:
            conn.execute(statement)
        result["table_created"] = existed is None

        conn.commit()
        result["reason"] = "additive migration applied; no rows were deleted"
        return result
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="path to the SQLite database")
    args = parser.parse_args()
    print(migrate(args.db))


if __name__ == "__main__":
    main()
