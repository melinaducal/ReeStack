import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_ROOT = Path(os.getenv("REEESTACK_UPLOAD_DIR") or (BASE_DIR / "uploads"))
AVATAR_DIR = UPLOAD_ROOT / "avatars"


def ensure_upload_dirs():
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    return AVATAR_DIR
