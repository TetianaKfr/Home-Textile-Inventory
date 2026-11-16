from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CompatibilityRule, HouseholdObject, Item
from app.services.places import location_catalog
from app.services.compatibility import (
    RANK,
    match_curtain,
    match_duvet_cover,
    match_fitted_sheet,
    match_flat_sheet,
    match_pillowcase,
    match_tablecloth,
    visual_score,
    worst_status,
)
from app.services.dimensions import size_label, usable_measure


def _attrs(item: Item) -> dict:
    data = {
        "width": item.width,
        "length": item.length,
        "height": item.height,
        "diameter": item.diameter,
        "shape": (item.attributes or {}).get("shape", ""),
        "attachment": (item.attributes or {}).get("attachment", ""),
        "overhang": (item.attributes or {}).get("overhang"),
        "mattress_depth": (item.attributes or {}).get("mattress_depth"),
        "panel_width": (item.attributes or {}).get("panel_width") or item.width,
        "panel_count": (item.attributes or {}).get("panel_count") or 1,
    }
    return data


def _object_dims(obj: HouseholdObject) -> dict:
    attrs = obj.attributes or {}
    return {
        "width": obj.width,
        "length": obj.length,
        "height": obj.height,
        "diameter": obj.diameter,
        "depth": obj.depth,
        "shape": obj.shape or attrs.get("shape") or "",
        "rail_width": attrs.get("rail_width"),
        "fullness": attrs.get("fullness"),
        "desired_length": attrs.get("desired_length"),
        "rail_to_floor": attrs.get("rail_to_floor"),
        "attachment": attrs.get("attachment") or "",
        "overhang": attrs.get("overhang"),
        "mattress_depth": obj.depth,
    }


def _usable_units(item: Item):
    return [
        unit
        for unit in item.units
        if not unit.archived and unit.status not in {"archived", "damaged"}
    ]


def _brief(item: Item, path, role: str, verdict: dict) -> dict:
    units = _usable_units(item)
    main = next((photo for photo in item.photos if photo.is_main), None) or (item.photos[0] if item.photos else None)
    return {
        "item_id": item.id,
        "name": item.name,
        "category": item.category.name if item.category else "",
        "slug": item.category.slug if item.category else "",
        "role": role,
        "dimensions": size_label(item.width, item.length, item.diameter),
        "primary_color": item.primary_color,
        "material": item.material,
        "pattern": item.pattern,
        "quantity": len(units),
        "statuses": sorted({unit.status for unit in units}),
        "locations": sorted({path(unit.location_id) for unit in units}),
        "photo_id": main.id if main else None,
        "technical": verdict,
    }


class _HomeScoped:
    """An inventory item limited to the units stored in one home."""

    def __init__(self, item: Item, units: list):
        self._item = item
        self.units = units

    def __getattr__(self, name):
        return getattr(self._item, name)


def _home_scope(homes, rooms, locations, home_id: int | None) -> tuple[set[int] | None, str]:
    if home_id is None:
        return None, "all homes"
    room_ids = {room.id for room in rooms if room.home_id == home_id}
    location_ids = {location.id for location in locations if location.room_id in room_ids}
    home = next((home for home in homes if home.id == home_id), None)
    return location_ids, home.name if home else "the selected home"


def _scope_to_home(items: list, location_ids: set[int] | None) -> list:
    if location_ids is None:
        return items
    scoped = []
    for item in items:
        units = [unit for unit in _usable_units(item) if unit.location_id in location_ids]
        if units:
            scoped.append(_HomeScoped(item, units))
    return scoped


def _load_items(db: Session, family_id: int) -> list[Item]:
    stmt = (
        select(Item)
        .where(Item.family_id == family_id, Item.archived.is_(False))
        .options(selectinload(Item.units), selectinload(Item.photos), selectinload(Item.category))
    )
    return [item for item in db.scalars(stmt) if _usable_units(item)]


def _by_slug(items: list[Item], slugs: set[str]) -> list[Item]:
    return [item for item in items if item.category and item.category.slug in slugs]


def build_match(db: Session, family_id: int, obj: HouseholdObject, overrides: dict | None, preferences: dict, home_id: int | None = None) -> dict:
    homes, rooms, locations, path = location_catalog(db, family_id)
    location_ids, home_label = _home_scope(homes, rooms, locations, home_id)
    items = _load_items(db, family_id)
    rules = list(db.scalars(select(CompatibilityRule).where(CompatibilityRule.family_id == family_id)))
    if rules:
        enabled = {rule.target_slug for rule in rules if rule.enabled}
        controlled = {rule.target_slug for rule in rules}
        items = [item for item in items if item.category.slug not in controlled or item.category.slug in enabled]
    items = _scope_to_home(items, location_ids)
    target = _object_dims(obj)
    prefs = dict(preferences or {})
    if overrides:
        prefs.update({key: value for key, value in overrides.items() if value is not None})
    overhang_default = not (overrides and overrides.get("table_overhang_cm") is not None) and target.get("overhang") is None
    fullness_default = not (overrides and overrides.get("curtain_fullness") is not None) and target.get("fullness") is None
    if obj.kind == "table":
        result = _match_table(obj, target, items, path, prefs, overhang_default)
    elif obj.kind == "window":
        result = _match_window(obj, target, items, path, prefs, fullness_default)
    else:
        result = _match_bed(obj, target, items, path, prefs, overhang_default)
    result["search_note"] = f"Textiles in this result are taken from {home_label}."
    result["search_home_id"] = home_id
    return result


def _pair_visual(anchor: Item, other: Item) -> tuple[int, str]:
    return visual_score(anchor.primary_color, anchor.pattern, other.primary_color, other.pattern)


def _match_table(obj, target, items, path, prefs, overhang_default) -> dict:
    cloths = []
    rejected = []
    for item in _by_slug(items, {"tablecloth"}):
        verdict = match_tablecloth(target, _attrs(item), prefs, overhang_default)
        payload = _brief(item, path, "tablecloth", verdict.as_dict())
        if verdict.status == "incompatible":
            rejected.append(payload)
        else:
            cloths.append(payload)
    cloths.sort(key=lambda row: (-RANK[row["technical"]["status"]], -row["technical"]["score"]))
    combinations = []
    for row in cloths[:8]:
        combinations.append(
            {
                "technical_status": row["technical"]["status"],
                "technical_score": row["technical"]["score"],
                "visual_score": None,
                "visual_explanation": "Visual comparison needs a second textile. This result is technical only.",
                "items": [row],
                "missing": [],
                "explanation": row["technical"]["explanation"],
            }
        )
    missing = []
    if not cloths:
        missing.append({"category": "Tablecloth", "reason": "No technically compatible tablecloth was found.", "required": row_required_table(target, prefs)})
    return _envelope(obj, combinations, rejected, missing, prefs)


def row_required_table(target, prefs) -> str:
    overhang = usable_measure(target.get("overhang"))
    if overhang is None:
        overhang = usable_measure(prefs.get("table_overhang_cm"))
    if (target.get("shape") or "") == "round":
        diameter = usable_measure(target.get("diameter"))
        if diameter is not None and overhang is not None:
            return f"about ⌀ {diameter + 2 * overhang:.0f} cm"
    width = usable_measure(target.get("width"))
    length = usable_measure(target.get("length"))
    if width is not None and length is not None and overhang is not None:
        return f"about {width + 2 * overhang:.0f} × {length + 2 * overhang:.0f} cm"
    return "Enter the table length and width. A negative size is not used."


def _match_window(obj, target, items, path, prefs, fullness_default) -> dict:
    found = []
    rejected = []
    for item in _by_slug(items, {"curtain", "drape", "sheer-curtain"}):
        verdict = match_curtain(target, _attrs(item), prefs, fullness_default)
        payload = _brief(item, path, "curtain", verdict.as_dict())
        (rejected if verdict.status == "incompatible" else found).append(payload)
    found.sort(key=lambda row: (-RANK[row["technical"]["status"]], -row["technical"]["score"]))
    combinations = [
        {
            "technical_status": row["technical"]["status"],
            "technical_score": row["technical"]["score"],
            "visual_score": None,
            "visual_explanation": "Curtain matching here is technical. Compare colors on the item cards before saving a set.",
            "items": [row],
            "missing": [],
            "explanation": row["technical"]["explanation"],
        }
        for row in found[:8]
    ]
    missing = []
    if not found:
        rail = usable_measure(target.get("rail_width"))
        if rail is None:
            rail = usable_measure(target.get("width"))
        fullness = usable_measure(target.get("fullness"))
        if fullness is None:
            fullness = usable_measure(prefs.get("curtain_fullness"))
        required = (
            f"about {rail * fullness:.0f} cm total width"
            if rail is not None and fullness is not None
            else "Enter the window width and the curtain length."
        )
        missing.append({"category": "Curtains", "reason": "No technically compatible curtains were found.", "required": required})
    return _envelope(obj, combinations, rejected, missing, prefs)


def _match_bed(obj, target, items, path, prefs, overhang_default) -> dict:
    mattress = {
        "width": target.get("width"),
        "length": target.get("length"),
        "depth": target.get("depth"),
    }
    sheets = []
    rejected = []
    for item in _by_slug(items, {"fitted-sheet"}):
        verdict = match_fitted_sheet(mattress, _attrs(item), prefs)
        row = _brief(item, path, "fitted_sheet", verdict.as_dict())
        (rejected if verdict.status == "incompatible" else sheets).append(row)
    for item in _by_slug(items, {"bed-sheet"}):
        verdict = match_flat_sheet(mattress, _attrs(item), prefs, overhang_default)
        row = _brief(item, path, "flat_sheet", verdict.as_dict())
        (rejected if verdict.status == "incompatible" else sheets).append(row)
    protectors = []
    for item in _by_slug(items, {"mattress-protector"}):
        verdict = match_fitted_sheet(mattress, _attrs(item), prefs)
        row = _brief(item, path, "mattress_protector", verdict.as_dict())
        (rejected if verdict.status == "incompatible" else protectors).append(row)

    duvet_pairs = []
    duvets = _by_slug(items, {"duvet"})
    covers = _by_slug(items, {"duvet-cover"})
    if not duvets:
        duvet_pairs.append(None)
    for duvet in duvets:
        pair_found = False
        for cover in covers:
            verdict = match_duvet_cover(_attrs(duvet), _attrs(cover), prefs)
            if verdict.status == "incompatible":
                rejected.append(_brief(cover, path, "duvet_cover", verdict.as_dict()))
                continue
            pair_found = True
            visual, visual_text = _pair_visual(duvet, cover)
            duvet_pairs.append(
                {
                    "status": verdict.status,
                    "score": verdict.score,
                    "visual": visual,
                    "visual_text": visual_text,
                    "rows": [
                        _brief(duvet, path, "duvet", {"status": "exact", "score": 100, "explanation": "Selected duvet from the inventory.", "discrepancies": [], "warnings": [], "rotated": False}),
                        _brief(cover, path, "duvet_cover", verdict.as_dict()),
                    ],
                }
            )
        if covers and not pair_found:
            duvet_pairs.append(
                {
                    "status": "possible",
                    "score": 40,
                    "visual": 50,
                    "visual_text": "",
                    "rows": [_brief(duvet, path, "duvet", {"status": "possible", "score": 40, "explanation": "No compatible cover was found for this duvet.", "discrepancies": [], "warnings": ["Cover missing."], "rotated": False})],
                    "missing_cover": True,
                }
            )
    if duvets and not covers:
        duvet_pairs = [
            {
                "status": "possible",
                "score": 40,
                "visual": 50,
                "visual_text": "",
                "rows": [_brief(duvet, path, "duvet", {"status": "possible", "score": 40, "explanation": "The duvet has no cover in the inventory.", "discrepancies": [], "warnings": [], "rotated": False})],
                "missing_cover": True,
            }
            for duvet in duvets[:3]
        ]

    pillow_sizes = _bed_pillow_sizes(obj)
    cases = _by_slug(items, {"pillowcase"})
    pillow_plan = _assign_bed_pillows(pillow_sizes, cases, path, prefs, rejected)
    guards = _assign_bed_pillows(
        pillow_sizes,
        _by_slug(items, {"pillow-protector"}),
        path,
        prefs,
        rejected,
        role="pillow_protector",
        category="Pillow protector",
        piece="pillow protector",
        optional=True,
    )

    sheets.sort(key=lambda row: (-RANK[row["technical"]["status"]], -row["technical"]["score"]))
    protectors.sort(key=lambda row: (-RANK[row["technical"]["status"]], -row["technical"]["score"]))
    duvet_pairs.sort(key=lambda pair: (-RANK[pair["status"]], -pair["score"], -pair["visual"]) if pair else (0, 0, 0))

    combinations = []
    sheet_choices = sheets[:3] or [None]
    duvet_choices = duvet_pairs[:3] or [None]
    for sheet in sheet_choices:
        for duvet_pair in duvet_choices:
            parts = []
            statuses = []
            visuals = []
            visual_bits = []
            missing = []
            if sheet is None:
                missing.append({"category": "Sheet", "reason": "No technically compatible fitted or flat sheet was found.", "required": size_label(mattress.get("width"), mattress.get("length"))})
            else:
                parts.append(sheet)
                statuses.append(sheet["technical"]["status"])
            if duvet_pair:
                parts.extend(duvet_pair["rows"])
                statuses.append(duvet_pair["status"])
                visuals.append(duvet_pair["visual"])
                if duvet_pair.get("visual_text"):
                    visual_bits.append(duvet_pair["visual_text"])
                if duvet_pair.get("missing_cover"):
                    missing.append({"category": "Duvet cover", "reason": "No compatible duvet cover was found.", "required": duvet_pair["rows"][0]["dimensions"]})
            if pillow_plan["rows"]:
                parts.extend(pillow_plan["rows"])
                if pillow_plan["status"]:
                    statuses.append(pillow_plan["status"])
                if pillow_plan["visual"] is not None:
                    visuals.append(pillow_plan["visual"])
                if pillow_plan["visual_text"]:
                    visual_bits.append(pillow_plan["visual_text"])
            if pillow_plan["missing"]:
                missing.extend(pillow_plan["missing"])
            if guards["rows"]:
                parts.extend(guards["rows"])
                if guards["status"]:
                    statuses.append(guards["status"])
            if guards["missing"]:
                missing.extend(guards["missing"])
            if protectors:
                parts.append(protectors[0])
                statuses.append(protectors[0]["technical"]["status"])
            elif obj.kind in {"bed", "mattress"}:
                missing.append({"category": "Mattress protector", "reason": "No compatible mattress protector was found. This piece is optional.", "required": size_label(mattress.get("width"), mattress.get("length"))})
            if not parts:
                continue
            technical = worst_status([status for status in statuses if status])
            if technical == "incompatible":
                continue
            visual = round(sum(visuals) / len(visuals)) if visuals else None
            anchor = sheet or (parts[0] if parts else None)
            if anchor and visual is None and len(parts) > 1:
                scores = []
                texts = []
                for other in parts[1:]:
                    if other["item_id"] == anchor["item_id"]:
                        continue
                    # Visual uses stored colors on the brief.
                    score, text = visual_score(anchor["primary_color"], "", other["primary_color"], "")
                    scores.append(score)
                    texts.append(text)
                if scores:
                    visual = round(sum(scores) / len(scores))
                    visual_bits.extend(texts)
            combinations.append(
                {
                    "technical_status": technical,
                    "technical_score": min((part["technical"]["score"] for part in parts), default=0),
                    "visual_score": visual,
                    "visual_explanation": " ".join(visual_bits) or "Not enough color information for a visual score.",
                    "items": parts,
                    "missing": missing,
                    "explanation": " ".join(part["technical"]["explanation"] for part in parts if part["technical"].get("explanation")),
                }
            )
    combinations.sort(key=lambda row: (-RANK[row["technical_status"]], -(row["visual_score"] or 0), -row["technical_score"]))
    # Drop duplicate item groupings.
    unique = []
    seen = set()
    for row in combinations:
        key = tuple(sorted(part["item_id"] for part in row["items"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) == 6:
            break
    top_missing = list(unique[0]["missing"]) if unique else list(pillow_plan["missing"]) + list(guards["missing"])
    if not sheets and not any(entry.get("category") == "Sheet" for entry in top_missing):
        top_missing.append(
            {
                "category": "Sheet",
                "reason": "No technically compatible fitted or flat sheet was found.",
                "required": size_label(mattress.get("width"), mattress.get("length")),
            }
        )
    return _envelope(obj, unique, rejected[:12], top_missing, prefs)


def _bed_pillow_sizes(obj: HouseholdObject) -> list[dict]:
    """Pillow sizes stored on this bed. A mattress has none."""
    if obj.kind != "bed":
        return []
    sizes = []
    for entry in (obj.attributes or {}).get("pillows") or []:
        if not isinstance(entry, dict):
            continue
        width = usable_measure(entry.get("width"))
        length = usable_measure(entry.get("length"))
        if width is None or length is None:
            continue
        sizes.append({"width": width, "length": length})
    return sizes


def _assign_bed_pillows(
    pillow_sizes,
    cases,
    path,
    prefs,
    rejected,
    role: str = "pillowcase",
    category: str = "Pillowcase",
    piece: str = "pillowcase",
    optional: bool = False,
) -> dict:
    """Each usable unit covers one bed pillow. Only an exact size counts."""
    if not pillow_sizes:
        return {"rows": [], "status": None, "visual": None, "visual_text": "", "missing": []}
    remaining = {case.id: len(_usable_units(case)) for case in cases}
    assignments = []
    statuses = []
    missing_sizes: list[list] = []
    for index, pillow in enumerate(pillow_sizes, start=1):
        best = None
        for case in cases:
            if remaining.get(case.id, 0) <= 0:
                continue
            verdict = match_pillowcase(pillow, _attrs(case), prefs)
            if verdict.status != "exact":
                continue
            rank = (RANK[verdict.status], verdict.score)
            if best is None or rank > best[0]:
                best = (rank, case, verdict)
        if best is None:
            _count_missing(missing_sizes, pillow["width"], pillow["length"])
            continue
        _, case, verdict = best
        remaining[case.id] -= 1
        technical = verdict.as_dict()
        label = size_label(pillow["width"], pillow["length"])
        technical["explanation"] = f"{technical['explanation']} Bed pillow {index}: {label}."
        assignments.append(_brief(case, path, role, technical))
        statuses.append(verdict.status)
    for case in cases:
        verdicts = [match_pillowcase(pillow, _attrs(case), prefs) for pillow in pillow_sizes]
        if any(verdict.status != "incompatible" for verdict in verdicts):
            continue
        technical = verdicts[0].as_dict()
        technical["explanation"] = f"The {piece} does not fit any pillow size on this bed."
        rejected.append(_brief(case, path, role, technical))
    missing = []
    for width, length, count in missing_sizes:
        if count == 1:
            reason = f"1 suitable {piece} is still missing."
        else:
            reason = f"{count} suitable {piece}s are still missing."
        if optional:
            reason += " This piece is optional."
        missing.append(
            {
                "category": category,
                "reason": reason,
                "required": size_label(width, length),
            }
        )
    return {
        "rows": assignments,
        "status": worst_status(statuses) if statuses else None,
        "visual": None,
        "visual_text": "",
        "missing": missing,
    }


def _count_missing(rows: list[list], width: float, length: float) -> None:
    for row in rows:
        if row[0] == width and row[1] == length:
            row[2] += 1
            return
    rows.append([width, length, 1])


def _envelope(obj: HouseholdObject, combinations, rejected, missing, prefs) -> dict:
    return {
        "object": {
            "id": obj.id,
            "name": obj.name,
            "kind": obj.kind,
            "shape": obj.shape,
            "width": obj.width,
            "length": obj.length,
            "height": obj.height,
            "diameter": obj.diameter,
            "depth": obj.depth,
            "attributes": obj.attributes or {},
        },
        "preferences_used": prefs,
        "preference_note": "Default overhangs and fullness ratios are suggestions until the household sets its own values.",
        "combinations": combinations,
        "rejected": rejected,
        "missing": missing,
    }
