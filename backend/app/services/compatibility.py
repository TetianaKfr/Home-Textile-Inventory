"""Deterministic technical compatibility, with visual scoring kept separate."""

from dataclasses import dataclass, field

from app.catalog import DEFAULT_PREFERENCES
from app.services.dimensions import fmt_cm, usable_measure

_MEASURE_KEYS = (
    "width", "length", "height", "diameter", "depth", "overhang", "mattress_depth",
    "rail_width", "fullness", "desired_length", "rail_to_floor", "panel_width", "panel_count",
)

RANK = {"exact": 3, "acceptable": 2, "possible": 1, "incompatible": 0}

NEUTRALS = {"white", "ivory", "cream", "beige", "sand", "grey", "gray", "black"}


@dataclass
class Verdict:
    status: str
    score: int
    explanation: str
    discrepancies: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rotated: bool = False

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "score": self.score,
            "explanation": self.explanation,
            "discrepancies": self.discrepancies,
            "warnings": self.warnings,
            "rotated": self.rotated,
        }


def _prefs(overrides: dict | None) -> dict:
    merged = dict(DEFAULT_PREFERENCES)
    if overrides:
        for key, value in overrides.items():
            if value is None or key not in merged:
                continue
            number = usable_measure(value)
            if number is None:
                continue
            merged[key] = number
    return merged


def _num(source: dict, key: str):
    return usable_measure(source.get(key))


def _measures(source: dict | None) -> dict:
    cleaned = dict(source or {})
    for key in _MEASURE_KEYS:
        if key in cleaned:
            cleaned[key] = usable_measure(cleaned.get(key))
    return cleaned


def _status_for_delta(max_delta: float, exact_at: float, acceptable_at: float, possible_at: float) -> str:
    if max_delta <= exact_at:
        return "exact"
    if max_delta <= acceptable_at:
        return "acceptable"
    if max_delta <= possible_at:
        return "possible"
    return "incompatible"


def _orientations(width: float, length: float) -> list[tuple[float, float, bool]]:
    pairs = [(width, length, False)]
    if abs(width - length) > 0.05:
        pairs.append((length, width, True))
    return pairs


def _missing(*values) -> bool:
    return any(value is None for value in values)


def visual_score(color_a: str, pattern_a: str, color_b: str, pattern_b: str) -> tuple[int, str]:
    left = (color_a or "").strip().lower()
    right = (color_b or "").strip().lower()
    pattern_left = (pattern_a or "").strip().lower()
    pattern_right = (pattern_b or "").strip().lower()
    reasons = []
    if not left or not right:
        score = 50
        reasons.append("One of the colors is unknown, so the visual score is only a hint.")
    elif left == right:
        score = 90
        reasons.append(f"Both pieces use {left}.")
    elif left in NEUTRALS or right in NEUTRALS:
        score = 78
        reasons.append("A neutral color keeps the pairing flexible.")
    else:
        score = 46
        reasons.append(f"{left.title()} and {right.title()} are not an obvious pairing.")
    if pattern_left == "plain" or pattern_right == "plain":
        score += 5
        reasons.append("A plain textile balances the other pattern.")
    elif pattern_left and pattern_right and pattern_left == pattern_right and pattern_left not in {"plain", "textured"}:
        score -= 6
        reasons.append("Both pieces share a patterned design, which can compete.")
    return max(0, min(100, score)), " ".join(reasons)


def match_fitted_sheet(mattress: dict, sheet: dict, preferences: dict | None = None) -> Verdict:
    mattress = _measures(mattress)
    sheet = _measures(sheet)
    prefs = _prefs(preferences)
    tol = float(prefs["size_tolerance_cm"])
    if _missing(mattress.get("width"), mattress.get("length"), sheet.get("width"), sheet.get("length")):
        return Verdict("possible", 40, "Fitted sheet or mattress dimensions are incomplete.", warnings=["Dimensions are missing."])
    best = None
    for width, length, rotated in _orientations(sheet["width"], sheet["length"]):
        delta_w = abs(width - mattress["width"])
        delta_l = abs(length - mattress["length"])
        candidate = (max(delta_w, delta_l), delta_w, delta_l, rotated, width, length)
        if best is None or candidate[0] < best[0]:
            best = candidate
    max_delta, delta_w, delta_l, rotated, width, length = best
    status = _status_for_delta(max_delta, 1, tol, tol + 5)
    warnings = []
    discrepancies = []
    if delta_w > 1 or delta_l > 1:
        discrepancies.append(
            f"Sheet {fmt_cm(width)} × {fmt_cm(length)} cm versus mattress "
            f"{fmt_cm(mattress['width'])} × {fmt_cm(mattress['length'])} cm."
        )
    mattress_depth = _num(mattress, "depth")
    sheet_depth = _num(sheet, "mattress_depth")
    if mattress_depth is None or sheet_depth is None:
        if status == "exact":
            status = "possible"
        elif status == "acceptable":
            status = "possible"
        warnings.append("Fitted corner height or mattress depth is not recorded, so the depth fit is unconfirmed.")
    elif sheet_depth + 1 < mattress_depth:
        short = mattress_depth - sheet_depth
        discrepancies.append(f"The sheet corner allows about {fmt_cm(sheet_depth)} cm, but the mattress is {fmt_cm(mattress_depth)} cm deep.")
        status = "possible" if short <= 3 and status != "incompatible" else "incompatible"
        warnings.append("The fitted sheet may not reach around the mattress.")
    if rotated:
        warnings.append("Width and length were compared after turning the sheet, because a sheet can be rotated.")
    explanation = {
        "exact": "The fitted sheet matches the mattress size.",
        "acceptable": "The fitted sheet is within the configured size tolerance.",
        "possible": "The fitted sheet might work, but a measurement should be confirmed.",
        "incompatible": "The fitted sheet does not fit this mattress.",
    }[status]
    score = {"exact": 100, "acceptable": 82, "possible": 55, "incompatible": 0}[status]
    return Verdict(status, score, explanation, discrepancies, warnings, rotated)


def match_flat_sheet(mattress: dict, sheet: dict, preferences: dict | None = None, overhang_is_default: bool = True) -> Verdict:
    mattress = _measures(mattress)
    sheet = _measures(sheet)
    prefs = _prefs(preferences)
    if _missing(mattress.get("width"), mattress.get("length"), sheet.get("width"), sheet.get("length")):
        return Verdict("possible", 40, "Flat sheet or mattress dimensions are incomplete.", warnings=["Dimensions are missing."])
    side = float(prefs["sheet_side_overhang_cm"])
    head = float(prefs["sheet_head_overhang_cm"])
    foot = float(prefs["sheet_foot_overhang_cm"])
    recommended_w = mattress["width"] + 2 * side
    recommended_l = mattress["length"] + head + foot
    best = None
    for width, length, rotated in _orientations(sheet["width"], sheet["length"]):
        delta = max(abs(width - recommended_w), abs(length - recommended_l))
        # Extra fabric is more acceptable than a sheet that is too small.
        short = max(0, recommended_w - width, recommended_l - length)
        candidate = (short, delta, rotated, width, length)
        if best is None or candidate < best:
            best = candidate
    short, delta, rotated, width, length = best
    tol = float(prefs["size_tolerance_cm"])
    if short > tol + 8:
        status = "incompatible"
    elif short > 1:
        status = "possible"
    elif delta <= 2:
        status = "exact"
    elif delta <= 20:
        status = "acceptable"
    else:
        status = "possible"
    warnings = []
    if overhang_is_default:
        warnings.append(
            f"Side overhang {fmt_cm(side)} cm and end overhangs {fmt_cm(head)} / {fmt_cm(foot)} cm "
            "are suggestions, not measurements from the household."
        )
    if rotated:
        warnings.append("Width and length were compared after turning the sheet.")
    discrepancies = [
        f"Recommended flat sheet is about {fmt_cm(recommended_w)} × {fmt_cm(recommended_l)} cm. "
        f"This sheet is {fmt_cm(width)} × {fmt_cm(length)} cm."
    ]
    explanation = {
        "exact": "The flat sheet is very close to the recommended size for this mattress.",
        "acceptable": "The flat sheet can cover this mattress with a usable overhang.",
        "possible": "The flat sheet is near the recommended size, but the overhang should be checked.",
        "incompatible": "The flat sheet is too small for the recommended overhang.",
    }[status]
    score = {"exact": 100, "acceptable": 80, "possible": 58, "incompatible": 0}[status]
    return Verdict(status, score, explanation, discrepancies, warnings, rotated)


def match_duvet_cover(duvet: dict, cover: dict, preferences: dict | None = None) -> Verdict:
    duvet = _measures(duvet)
    cover = _measures(cover)
    prefs = _prefs(preferences)
    tol = float(prefs["duvet_tolerance_cm"])
    if _missing(duvet.get("width"), duvet.get("length"), cover.get("width"), cover.get("length")):
        return Verdict("possible", 40, "Duvet or cover dimensions are incomplete.", warnings=["Dimensions are missing."])
    best = None
    for width, length, rotated in _orientations(cover["width"], cover["length"]):
        delta_w = width - duvet["width"]
        delta_l = length - duvet["length"]
        short = max(0, -delta_w, -delta_l)
        over = max(0, delta_w, delta_l)
        candidate = (short, over, rotated, width, length, delta_w, delta_l)
        if best is None or candidate[:3] < best[:3]:
            best = candidate
    short, over, rotated, width, length, delta_w, delta_l = best
    if short <= 1 and over <= 1:
        status = "exact"
    elif short <= 1 and over <= tol:
        status = "acceptable"
    elif short <= tol and over <= tol * 3:
        status = "possible"
    elif short == 0 and over <= tol * 3:
        status = "possible"
    else:
        status = "incompatible"
    discrepancies = []
    if abs(delta_w) > 1 or abs(delta_l) > 1:
        discrepancies.append(
            f"Cover {fmt_cm(width)} × {fmt_cm(length)} cm versus duvet "
            f"{fmt_cm(duvet['width'])} × {fmt_cm(duvet['length'])} cm."
        )
    warnings = []
    if status == "possible":
        warnings.append("The size difference is outside a close match. Confirm it before use.")
    if rotated:
        warnings.append("Width and length were compared after turning the cover, which a duvet allows.")
    explanation = {
        "exact": "The duvet cover is an exact size match.",
        "acceptable": "The duvet cover is within the configured tolerance.",
        "possible": "The duvet cover is close, but the difference may be unsuitable.",
        "incompatible": "The duvet cover does not match this duvet. A size difference is not treated as acceptable by default.",
    }[status]
    score = {"exact": 100, "acceptable": 84, "possible": 52, "incompatible": 0}[status]
    return Verdict(status, score, explanation, discrepancies, warnings, rotated)


def match_pillowcase(pillow: dict, case: dict, preferences: dict | None = None) -> Verdict:
    pillow = _measures(pillow)
    case = _measures(case)
    prefs = _prefs(preferences)
    allowance = float(prefs["pillow_allowance_cm"])
    if _missing(pillow.get("width"), pillow.get("length"), case.get("width"), case.get("length")):
        return Verdict("possible", 40, "Pillow or pillowcase dimensions are incomplete.", warnings=["Dimensions are missing."])
    best = None
    for width, length, rotated in _orientations(case["width"], case["length"]):
        slack_w = width - pillow["width"]
        slack_l = length - pillow["length"]
        short = max(0, -slack_w, -slack_l)
        loose = max(0, slack_w, slack_l)
        candidate = (short, loose, rotated, width, length)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    short, loose, rotated, width, length = best
    if short > 2:
        status = "incompatible"
    elif loose <= 2 and short <= 1:
        status = "exact"
    elif loose <= allowance and short <= 1:
        status = "acceptable"
    elif loose <= allowance + 7 and short <= 2:
        status = "possible"
    else:
        status = "incompatible"
    warnings = []
    discrepancies = [
        f"Pillowcase {fmt_cm(width)} × {fmt_cm(length)} cm versus pillow "
        f"{fmt_cm(pillow['width'])} × {fmt_cm(pillow['length'])} cm."
    ]
    if status == "possible":
        warnings.append("The allowance is larger than a typical close fit. Confirm with the manufacturer if needed.")
    if rotated:
        warnings.append("Width and length were compared after turning the pillowcase.")
    explanation = {
        "exact": "The pillowcase is a close fit for this pillow.",
        "acceptable": "The pillowcase fits within the usual allowance.",
        "possible": "The pillowcase might fit, but the allowance should be confirmed.",
        "incompatible": "The pillowcase does not fit this pillow.",
    }[status]
    score = {"exact": 100, "acceptable": 84, "possible": 55, "incompatible": 0}[status]
    return Verdict(status, score, explanation, discrepancies, warnings, rotated)


def match_tablecloth(table: dict, cloth: dict, preferences: dict | None = None, overhang_is_default: bool = True) -> Verdict:
    table = _measures(table)
    cloth = _measures(cloth)
    prefs = _prefs(preferences)
    overhang = _num(table, "overhang")
    if overhang is None:
        overhang = _num(cloth, "overhang")
    if overhang is None:
        overhang = float(prefs["table_overhang_cm"])
        using_default = True
    else:
        using_default = overhang_is_default and _num(table, "overhang") is None
    table_shape = _shape_name(table.get("shape") or "rectangular")
    cloth_shape = _shape_name(cloth.get("shape") or "")
    warnings = []
    if using_default:
        warnings.append(f"Overhang of {fmt_cm(overhang)} cm is a suggestion until you set a preferred drop.")
    if table_shape in {"round"}:
        if cloth_shape and cloth_shape not in {"round"}:
            return Verdict("incompatible", 0, "A round table needs a round tablecloth.", warnings=warnings)
        if _missing(table.get("diameter"), cloth.get("diameter")):
            return Verdict("possible", 40, "Table or tablecloth diameter is missing.", warnings=["Diameter is missing."] + warnings)
        recommended = table["diameter"] + 2 * overhang
        delta = cloth["diameter"] - recommended
        status = _table_status(delta)
        discrepancies = [f"Recommended diameter {fmt_cm(recommended)} cm. This cloth is ⌀ {fmt_cm(cloth['diameter'])} cm."]
    else:
        if table_shape == "square" and cloth_shape == "round":
            return Verdict("incompatible", 0, "A round cloth does not match a square table.", warnings=warnings)
        if table_shape == "rectangular" and cloth_shape == "round":
            return Verdict("incompatible", 0, "A round cloth does not match a rectangular table.", warnings=warnings)
        if cloth_shape == "oval" and table_shape not in {"oval", "rectangular"}:
            return Verdict("possible", 50, "An oval cloth is only a cautious match for this table shape.", warnings=warnings)
        if _missing(table.get("width"), table.get("length"), cloth.get("width"), cloth.get("length")):
            return Verdict("possible", 40, "Table or tablecloth dimensions are incomplete.", warnings=["Dimensions are missing."] + warnings)
        recommended_w = table["width"] + 2 * overhang
        recommended_l = table["length"] + 2 * overhang
        best = None
        for width, length, rotated in _orientations(cloth["width"], cloth["length"]):
            delta = max(abs(width - recommended_w), abs(length - recommended_l))
            short = max(0, recommended_w - width, recommended_l - length)
            candidate = (short, delta, rotated, width, length)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        short, delta, rotated, width, length = best
        status = "incompatible" if short > 8 else _table_status(delta if short <= 1 else short + 2)
        if rotated:
            warnings.append("The tablecloth was turned to follow the table.")
        discrepancies = [
            f"Recommended tablecloth {fmt_cm(recommended_w)} × {fmt_cm(recommended_l)} cm. "
            f"This cloth is {fmt_cm(width)} × {fmt_cm(length)} cm."
        ]
        if table_shape == "oval" and cloth_shape != "oval":
            warnings.append("An oval table is being compared with a cloth that is not marked as oval.")
            if status == "exact":
                status = "acceptable"
    explanation = {
        "exact": "The tablecloth matches the table shape and the overhang calculation.",
        "acceptable": "The tablecloth is close to the size calculated from the table and overhang.",
        "possible": "The tablecloth is only a partial match. Check the drop on the table.",
        "incompatible": "The tablecloth does not fit this table's shape or size.",
    }[status]
    score = {"exact": 100, "acceptable": 82, "possible": 54, "incompatible": 0}[status]
    return Verdict(status, score, explanation, discrepancies, warnings)


def _shape_name(value: str) -> str:
    shape = (value or "").strip().lower()
    if shape in {"carre", "carré"}:
        return "square"
    return shape


def _table_status(delta: float) -> str:
    gap = abs(delta)
    if gap <= 2:
        return "exact"
    if gap <= 8:
        return "acceptable"
    if gap <= 15:
        return "possible"
    return "incompatible"


def match_curtain(window: dict, curtain: dict, preferences: dict | None = None, fullness_is_default: bool = True) -> Verdict:
    window = _measures(window)
    curtain = _measures(curtain)
    prefs = _prefs(preferences)
    warnings = []
    rail = _num(window, "rail_width")
    used_window_width = False
    if rail is None:
        rail = _num(window, "width")
        used_window_width = True
        if rail is None:
            return Verdict("possible", 35, "Neither curtain rail width nor window width is recorded.", warnings=["Width is missing."])
        warnings.append("Curtain rail width is missing, so the window width was used. This is less reliable.")
    fullness = _num(window, "fullness")
    if fullness is None:
        fullness = float(prefs["curtain_fullness"])
        if fullness_is_default:
            warnings.append(f"Fullness ratio {fullness:g} is a suggestion for this curtain type.")
    panel_width = _num(curtain, "panel_width") or _num(curtain, "width")
    panel_count = _num(curtain, "panel_count") or 1
    if panel_width is None:
        return Verdict("possible", 40, "Curtain panel width is not recorded.", warnings=["Panel width is missing."])
    actual = panel_width * panel_count
    recommended = rail * fullness
    ratio = actual / recommended if recommended else 0
    if 0.9 <= ratio <= 1.1:
        status = "exact"
    elif 0.8 <= ratio <= 1.25:
        status = "acceptable"
    elif 0.65 <= ratio <= 1.45:
        status = "possible"
    else:
        status = "incompatible"
    desired_length = _num(window, "desired_length") or _num(window, "rail_to_floor")
    curtain_length = _num(curtain, "length")
    discrepancies = [
        f"Recommended total curtain width is {fmt_cm(recommended)} cm "
        f"({fmt_cm(rail)} cm rail × {fullness:g}). Available width is {fmt_cm(actual)} cm."
    ]
    if not used_window_width:
        discrepancies.append("The rail width was used instead of the window width.")
    if desired_length and curtain_length:
        length_gap = abs(curtain_length - desired_length)
        discrepancies.append(f"Curtain length {fmt_cm(curtain_length)} cm versus desired {fmt_cm(desired_length)} cm.")
        if length_gap > 30:
            status = "incompatible"
        elif length_gap > 15 and status in {"exact", "acceptable"}:
            status = "possible"
        elif length_gap > 5 and status == "exact":
            status = "acceptable"
    elif curtain_length is None or desired_length is None:
        warnings.append("Curtain length or the desired drop is missing, so the length was not fully checked.")
        if status == "exact":
            status = "possible"
    window_attachment = (window.get("attachment") or "").strip().lower()
    curtain_attachment = (curtain.get("attachment") or "").strip().lower()
    if window_attachment and curtain_attachment and window_attachment != curtain_attachment:
        warnings.append(
            f"Attachment differs: window needs {window_attachment}, curtain has {curtain_attachment}."
        )
        if status in {"exact", "acceptable"}:
            status = "possible"
    elif not window_attachment or not curtain_attachment:
        warnings.append("Attachment type is incomplete, so heading compatibility is unconfirmed.")
    explanation = {
        "exact": "The curtains match the rail width, fullness, length, and attachment.",
        "acceptable": "The curtains are within a practical range of the rail calculation.",
        "possible": "The curtains might work, but width, length, or attachment should be confirmed.",
        "incompatible": "The curtains do not satisfy the rail, length, or fullness requirements.",
    }[status]
    score = {"exact": 100, "acceptable": 80, "possible": 56, "incompatible": 0}[status]
    return Verdict(status, score, explanation, discrepancies, warnings)


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "possible"
    return min(statuses, key=lambda status: RANK[status])
