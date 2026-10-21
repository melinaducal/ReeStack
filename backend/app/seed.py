"""Idempotent demo seed: catalog items and clearly-marked example posts.

Demo users are marked by a non-verifiable password hash, so they cannot
be logged into. Demo posts carry `is_demo=True` and are labelled in the
UI as example content, not real community activity.
"""
import hashlib
from sqlmodel import Session, select

from .models import Content, Post, User

CATALOG = [
    ("The Creative Act", "Rick Rubin", "book", 2023, "A practical meditation on the creative process and how attention shapes what we make.", "creative-act", 432, "pages", ["creativity", "craft"]),
    ("Interstellar", "Christopher Nolan", "movie", 2014, "A team of explorers travels through a wormhole in space in an attempt to ensure humanity's survival.", "interstellar", 169, "minutes", ["science", "space"]),
    ("Kind of Blue", "Miles Davis", "music", 1959, "A landmark modal jazz record whose spacious arrangements still reward deep listening.", "kind-of-blue", 5, "tracks", ["jazz", "classic"]),
    ("Attention Is All You Need", "Vaswani et al.", "paper", 2017, "The transformer architecture paper that introduced scaled dot-product attention for sequence transduction.", "attention", 11, "pages", ["machine learning", "transformers"]),
    ("Severance", "Dan Erickson", "series", 2022, "Office workers whose memories are surgically divided between work and personal life begin to question the arrangement.", "severance", 19, "episodes", ["mystery", "drama"]),
    ("The Midnight Library", "Matt Haig", "book", 2020, "A library between life and death lets a woman explore the lives she could have lived.", "midnight-library", 304, "pages", ["fiction", "philosophy"]),
    ("Cosmos", "Carl Sagan", "book", 1980, "A sweeping tour of the universe and our place within it, written to make science feel personal.", "cosmos", 365, "pages", ["science", "astronomy"]),
    ("Dune", "Frank Herbert", "book", 1965, "Politics, ecology, and prophecy collide on the desert planet Arrakis.", "dune", 688, "pages", ["science fiction", "ecology"]),
    ("In Rainbows", "Radiohead", "music", 2007, "A warm, rhythm-driven record that balances intimacy with restless experiment.", "in-rainbows", 10, "tracks", ["alternative", "electronic"]),
    ("Slow Horses", "Will Smith", "series", 2022, "Dismissed British intelligence agents stumble into real conspiracies from the margins of MI5.", "slow-horses", 24, "episodes", ["spy", "drama"]),
]

DEMO_POSTS = [
    ("demo_mara", "Mara K.", "Halfway through Cosmos and I keep underlining whole paragraphs. Sagan makes the scale of the universe feel intimate instead of frightening.", "cosmos", 5),
    ("demo_jon", "Jon Bell", "Started Severance on the train and now I am suspicious of every elevator. The premise gets more uncomfortable the more ordinary it looks.", "severance", None),
    ("demo_ivy", "Ivy Chen", "Listening to Kind of Blue while working through a methods section. Silence between the notes is doing half the thinking for me.", "kind-of-blue", None),
    ("demo_theo", "Theo Marsh", "Three papers deep on attention mechanisms today. Rereading the original transformer paper is a good reminder that clarity is a design choice.", "attention", None),
]


def _demo_password_hash() -> str:
    # Deterministic unusable placeholder: verification always fails.
    return "demo:" + hashlib.sha256(b"reesatck-demo-not-a-login").hexdigest()


def seed_demo(session: Session) -> None:
    existing_contents = session.exec(select(Content)).first()
    if existing_contents is not None:
        return

    contents_by_title = {}
    for title, creator, kind, year, description, cover_key, total, unit, tags in CATALOG:
        content = Content(
            title=title,
            creator=creator,
            kind=kind,
            year=year,
            description=description,
            cover_key=cover_key,
            total_units=total,
            unit_label=unit,
            tags=str(tags).replace("'", '"'),
        )
        session.add(content)
        contents_by_title[title] = content
    session.flush()

    for username, display_name, body, cover_key, rating in DEMO_POSTS:
        user = User(
            username=username,
            display_name=display_name,
            password_hash=_demo_password_hash(),
            bio="Example community member.",
            avatar_color="#8a9e8f",
        )
        session.add(user)
        session.flush()
        content_id = None
        for content in contents_by_title.values():
            if content.cover_key == cover_key:
                content_id = content.id
                break
        session.add(
            Post(
                user_id=user.id,
                body=body,
                content_id=content_id,
                rating=rating,
                is_demo=True,
            )
        )
    session.commit()
