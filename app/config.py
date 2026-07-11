"""Shared paths and settings. Everything lives locally under data/."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "receipts.db"

# allowed upload types
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def ensure_dirs() -> None:
    """Create the local data folders on first run."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
