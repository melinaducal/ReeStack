import sqlite3

import migrate_posts


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            type TEXT NOT NULL,
            title TEXT,
            creator TEXT,
            pages INTEGER,
            year INTEGER,
            thoughts TEXT,
            cover_url TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO items (id, user_id, type, title, creator, pages, year, thoughts)"
        " VALUES (17, 5, 'book', 'Una reflexión', NULL, NULL, NULL, '<p>Hola</p>')"
    )
    conn.execute(
        "INSERT INTO items (id, user_id, type, title, creator, pages, year, thoughts)"
        " VALUES (18, 5, 'book', 'El Quijote', 'Cervantes', 863, 1605, 'Novela.')"
    )
    conn.commit()
    conn.close()


def _type_of(path, item_id):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT type FROM items WHERE id = ?", (item_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_report_is_read_only(tmp_path):
    db = tmp_path / "report.db"
    _make_db(db)

    result = migrate_posts.report(db)

    assert [candidate["id"] for candidate in result["candidates"]] == [17]
    assert result["candidates"][0]["current_type"] == "book"
    assert result["candidates"][0]["has_rich_text"] is True
    assert _type_of(db, 17) == "book"


def test_apply_changes_only_explicit_ids_and_keeps_backup(tmp_path):
    db = tmp_path / "apply.db"
    _make_db(db)

    result = migrate_posts.apply([17], db)

    assert result["changed"] == [{"id": 17, "from": "book", "to": "post"}]
    assert _type_of(db, 17) == "post"
    assert _type_of(db, 18) == "book"

    conn = sqlite3.connect(db)
    try:
        backup = conn.execute(
            "SELECT item_id, previous_type, new_type FROM item_type_migrations"
        ).fetchall()
    finally:
        conn.close()
    assert backup == [(17, "book", "post")]


def test_apply_is_idempotent(tmp_path):
    db = tmp_path / "idempotent.db"
    _make_db(db)
    migrate_posts.apply([17], db)

    result = migrate_posts.apply([17], db)

    assert result["changed"] == []
    assert result["skipped"] == [{"id": 17, "reason": "already post"}]


def test_apply_rejects_unknown_or_unexpected_rows(tmp_path):
    db = tmp_path / "reject.db"
    _make_db(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO items (id, user_id, type, title, thoughts)"
        " VALUES (19, 5, 'article', 'Raro', '<p>x</p>')"
    )
    conn.commit()
    conn.close()

    result = migrate_posts.apply([999, 19], db)

    assert result["changed"] == []
    assert result["skipped"] == [
        {"id": 19, "reason": "unexpected type: article"},
        {"id": 999, "reason": "not found"},
    ]


def test_rollback_restores_previous_types(tmp_path):
    db = tmp_path / "rollback.db"
    _make_db(db)
    migrate_posts.apply([17], db)

    result = migrate_posts.rollback(db)

    assert result["restored"] == [{"id": 17, "restored_type": "book"}]
    assert _type_of(db, 17) == "book"
    conn = sqlite3.connect(db)
    try:
        count = conn.execute("SELECT COUNT(*) FROM item_type_migrations").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_apply_without_ids_does_nothing(tmp_path):
    db = tmp_path / "empty.db"
    _make_db(db)

    result = migrate_posts.apply([], db)

    assert result["changed"] == []
    assert result["reason"] == "no ids provided"
    assert _type_of(db, 17) == "book"
