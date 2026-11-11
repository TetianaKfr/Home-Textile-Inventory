import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from app.config import get_settings


def save_photo(data: bytes, family_id: int) -> tuple[str, str]:
    try:
        image = Image.open(BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise ValueError("Upload a JPEG, PNG, or WebP photograph") from exc

    full = image.copy()
    full.thumbnail((1600, 1600))
    thumb = image.copy()
    thumb.thumbnail((480, 480))

    folder = Path(get_settings().storage_dir) / str(family_id)
    folder.mkdir(parents=True, exist_ok=True)
    stem = uuid.uuid4().hex
    full_rel = f"{family_id}/{stem}.jpg"
    thumb_rel = f"{family_id}/{stem}_thumb.jpg"
    full.save(folder / f"{stem}.jpg", format="JPEG", quality=85)
    thumb.save(folder / f"{stem}_thumb.jpg", format="JPEG", quality=80)
    return full_rel, thumb_rel


def absolute_path(relative: str) -> Path:
    root = Path(get_settings().storage_dir).resolve()
    path = (root / relative).resolve()
    if root not in path.parents and path != root:
        raise ValueError("Invalid photo path")
    return path
