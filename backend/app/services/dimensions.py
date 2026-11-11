import re

_NUMBER = r"(\d+(?:[.,]\d+)?)"
_PAIR = re.compile(rf"^\s*{_NUMBER}\s*(?:x|×|/|by)\s*{_NUMBER}\s*$", re.IGNORECASE)


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def parse_dimension_pair(text: str) -> tuple[float, float] | None:
    """Parse a width-then-length pair. The first number stays width; values are not swapped."""
    if not text:
        return None
    normalized = text.strip().lower().replace("×", "x").replace("на", "x")
    match = _PAIR.match(normalized)
    if not match:
        return None
    return _to_float(match.group(1)), _to_float(match.group(2))


def fmt_cm(value: float | None) -> str:
    if value is None:
        return "unknown"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def size_label(width: float | None, length: float | None, diameter: float | None = None) -> str:
    if diameter:
        return f"⌀ {fmt_cm(diameter)} cm"
    if width and length:
        return f"{fmt_cm(width)} × {fmt_cm(length)} cm"
    if width:
        return f"width {fmt_cm(width)} cm"
    if length:
        return f"length {fmt_cm(length)} cm"
    return "dimensions not recorded"
