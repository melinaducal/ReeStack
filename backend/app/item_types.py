from typing import Literal

# A social post is its own kind of content. It must never be inferred from the
# text or the HTML: the client has to send it explicitly when creating it.
POST_TYPE = "post"

CULTURAL_ITEM_TYPES = ("book", "movie", "series", "music", "paper")

ITEM_TYPES = (*CULTURAL_ITEM_TYPES, POST_TYPE)

ItemType = Literal["book", "movie", "series", "music", "paper", "post"]


def is_post_type(value: str | None) -> bool:
    return value == POST_TYPE
