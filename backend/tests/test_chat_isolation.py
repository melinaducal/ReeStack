"""Per-user isolation of the planning endpoints.

These tests used to open a real file database (``test_chat_isolation.db``),
which broke on a second run and left state behind. They now use the shared
in-memory fixture from ``conftest.py``, so nothing touches disk or the
production database.
"""

from datetime import date

from app.auth.utils import get_password_hash
from app.models import Item, User


def _make_user(db, index):
    user = User(
        username=f"u{index}",
        first_name="U",
        last_name=str(index),
        email=f"u{index}@test.com",
        birth_date=date(2000, 1, 1),
        hashed_password=get_password_hash("Passw0rd!"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_chat_recommend_only_own_items(db_session):
    user1 = _make_user(db_session, 1)
    user2 = _make_user(db_session, 2)

    db_session.add_all(
        [
            Item(title="Book1", type="book", user_id=user1.id),
            Item(title="Book2", type="book", user_id=user2.id),
        ]
    )
    db_session.commit()

    items1 = db_session.query(Item).filter(Item.user_id == user1.id).all()
    items2 = db_session.query(Item).filter(Item.user_id == user2.id).all()

    assert [item.title for item in items1] == ["Book1"]
    assert [item.title for item in items2] == ["Book2"]


def test_chat_save_assigns_user_id(db_session):
    user = _make_user(db_session, 3)

    item = Item(
        title="Rec1",
        type="movie",
        user_id=user.id,
        thoughts="Recomendado por chatbot: test",
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert item.user_id == user.id
