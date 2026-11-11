"""Local visual estimates. Measurements, brands, and materials are never invented."""

from io import BytesIO

from PIL import Image, ImageStat

NAMED_COLORS = {
    "white": (245, 245, 242),
    "ivory": (250, 244, 220),
    "cream": (245, 235, 200),
    "beige": (220, 200, 170),
    "sand": (210, 180, 140),
    "grey": (150, 150, 150),
    "black": (30, 30, 30),
    "navy": (30, 45, 90),
    "blue": (50, 100, 180),
    "light blue": (150, 190, 220),
    "green": (50, 120, 80),
    "sage": (150, 165, 140),
    "pink": (220, 150, 165),
    "red": (175, 45, 45),
    "burgundy": (120, 30, 45),
    "yellow": (225, 195, 60),
    "gold": (190, 150, 50),
    "orange": (210, 120, 45),
    "brown": (120, 80, 45),
    "purple": (110, 60, 140),
}

DISCLAIMER = (
    "This is an approximate visual estimate from the photograph. "
    "Lighting and camera settings can change the result. "
    "Measurements, fabric composition, and brand were not inferred."
)


def _nearest_color(rgb: tuple[float, float, float]) -> str:
    best_name = "unknown"
    best_dist = 10**9
    for name, target in NAMED_COLORS.items():
        dist = sum((a - b) ** 2 for a, b in zip(rgb, target))
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def suggest_from_bytes(data: bytes) -> dict:
    try:
        image = Image.open(BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise ValueError("The file is not a readable photograph") from exc

    width, height = image.size
    crop = image.crop((width * 0.25, height * 0.25, width * 0.75, height * 0.75))
    average = crop.resize((1, 1)).getpixel((0, 0))
    sample = image.convert("L").resize((64, 64))
    stddev = ImageStat.Stat(sample).stddev[0]
    pattern = "plain" if stddev < 18 else "patterned"
    color = _nearest_color(average)

    suggestions = {
        "primary_color": color,
        "pattern": pattern if pattern == "plain" else "",
        "texture": "textured" if stddev >= 28 else "",
    }
    # A patterned surface is reported as unconfirmed rather than given a specific motif.
    notes = []
    if pattern != "plain":
        notes.append("The photograph looks patterned. The exact motif was not identified.")
    notes.append(DISCLAIMER)

    return {
        "suggestions": {key: value for key, value in suggestions.items() if value},
        "unknown": ["category", "material", "brand", "width", "length", "height", "diameter"],
        "confidence": "low",
        "disclaimer": " ".join(notes),
        "field_sources": {key: "ai" for key, value in suggestions.items() if value},
    }
