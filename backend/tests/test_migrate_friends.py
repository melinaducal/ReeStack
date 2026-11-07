"""Tests for the additive friends/notifications migration."""

import sqlite3

import pytest

import migrate_friends_notifications

LEGACY_SCHEMA = """
CREATE TABLE friendships (
    id INTEGER NOT NULL,
    requester_id INTEGER NOT NULL,
    addressee_id INTEGER NOT NULL,
    status VARCHAR DEFAULT 'pending' NOT NULL,
    created_at DATETIME NOT NULL,
    responded_at DATETIME,
    PRIMARY KEY (id),
    CONSTRAINT uq_friendship_pair UNIQUE (requester_id, addressee_id),
    CONSTRAINT ck_friendship_not_self CHECK (requester_id <> addressee_id)
)
"""


def _make_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(LEGACY_SCHEMA)
    for requester_id, addressee_id, status in rows:
        conn.execute(
            "INSERT INTO friendships (requester_id, addressee_id, status, created_at)"
            " VALUES (?, ?, ?, '2026-01-01 00:00:00')",
            (requester_id, addressee_id, status),
        )
    conn.commit()
    conn.close()


def _index_names(path):
    conn = sqlite3.connect(path)
    try:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    finally:
        conn.close()


def _rows(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT requester_id, addressee_id, status FROM friendships"
            " ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_migration_adds_canonical_index_without_touching_rows(tmp_path):
    db = tmp_path / "legacy.db"
    _make_db(db, [(1, 2, "pending")])

    result = migrate_friends_notifications.migrate(db)

    assert result["canonical_index_created"] is True
    assert "uq_friendship_canonical_pair" in _index_names(db)
    assert _rows(db) == [(1, 2, "pending")]


def test_migration_index_blocks_mirrored_rows(tmp_path):
    db = tmp_path / "blocked.db"
    _make_db(db, [(1, 2, "pending")])
    migrate_friends_notifications.migrate(db)

    conn = sqlite3.connect(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO friendships (requester_id, addressee_id, status, created_at)"
                " VALUES (2, 1, 'pending', '2026-01-02 00:00:00')"
            )
    finally:
        conn.close()


def test_migration_is_idempotent(tmp_path):
    db = tmp_path / "idempotent.db"
    _make_db(db, [(1, 2, "accepted")])

    first = migrate_friends_notifications.migrate(db)
    second = migrate_friends_notifications.migrate(db)

    assert first["canonical_index_created"] is True
    assert second["canonical_index_created"] is False
    assert second["reason"] == "tables and unique index already exist; nothing to do"
    assert _rows(db) == [(1, 2, "accepted")]


def test_migration_refuses_to_delete_legacy_duplicates(tmp_path):
    db = tmp_path / "duplicates.db"
    _make_db(db, [(1, 2, "pending"), (2, 1, "accepted")])

    with pytest.raises(RuntimeError, match="duplicados"):
        migrate_friends_notifications.migrate(db)

    assert "uq_friendship_canonical_pair" not in _index_names(db)
    assert _rows(db) == [(1, 2, "pending"), (2, 1, "accepted")]


def test_migration_creates_tables_and_index_on_empty_database(tmp_path):
    db = tmp_path / "fresh.db"

    result = migrate_friends_notifications.migrate(db)

    assert set(result["created"]) == {"friendships", "notifications"}
    assert result["canonical_index_created"] is False  # created with the table
    assert "uq_friendship_canonical_pair" in _index_names(db)
