import csv
import io
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.catalog import STATUSES
from app.database import get_db
from app.deps import Context, bearer, get_context, require_role
from app.models import Category, CompatibilityRule, FamilyGroup, Item, ItemUnit, Membership, Photo, User
from app.security import decode_token
from app.serialize import category_dict, item_dict
from app.services.activity import add_audit, add_history, notify_family
from app.services.dimensions import parse_dimension_pair, size_label
from app.services.images import absolute_path, save_photo
from app.services.places import location_catalog
from app.services.vision import suggest_from_bytes

router = APIRouter(prefix="/api")

TRACKED = [
    "name", "description", "brand", "primary_color", "secondary_colors", "pattern", "texture",
    "material", "seasonality", "notes", "width", "length", "height", "diameter", "attributes", "category_id",
]


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=80)
    group_name: str = ""
    dimensions: list[str] = []
    fields: list[dict] = []


class ItemIn(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    brand: str = ""
    primary_color: str = ""
    secondary_colors: list[str] = []
    pattern: str = ""
    texture: str = ""
    material: str = ""
    seasonality: str = ""
    notes: str = ""
    width: float | None = None
    length: float | None = None
    height: float | None = None
    diameter: float | None = None
    attributes: dict = {}
    field_sources: dict = {}
    dimension_text: str | None = None
    location_id: int | None = None
    unit_status: str = "available"
    quantity: int = Field(default=1, ge=1, le=200)
    acknowledge_duplicates: bool = False


class ItemUpdate(BaseModel):
    version: int
    category_id: int | None = None
    name: str | None = None
    description: str | None = None
    brand: str | None = None
    primary_color: str | None = None
    secondary_colors: list[str] | None = None
    pattern: str | None = None
    texture: str | None = None
    material: str | None = None
    seasonality: str | None = None
    notes: str | None = None
    width: float | None = None
    length: float | None = None
    height: float | None = None
    diameter: float | None = None
    attributes: dict | None = None
    field_sources: dict | None = None
    dimension_text: str | None = None
    quantity: int | None = Field(default=None, ge=1, le=200)
    added_unit_location_id: int | None = None


class UnitIn(BaseModel):
    location_id: int | None = None
    status: str = "available"
    notes: str = ""
    quantity: int = Field(default=1, ge=1, le=100)


class UnitUpdate(BaseModel):
    location_id: int | None = None
    status: str | None = None
    notes: str | None = None
    clear_location: bool = False


def _visible_categories(ctx: Context) -> list[Category]:
    stmt = select(Category).where(
        Category.archived.is_(False),
        or_(Category.family_id.is_(None), Category.family_id == ctx.family.id),
    ).order_by(Category.group_name, Category.name)
    return list(ctx.db.scalars(stmt))


def _category_or_404(ctx: Context, category_id: int) -> Category:
    category = ctx.db.get(Category, category_id)
    if category is None or category.archived or (category.family_id not in {None, ctx.family.id}):
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def _load_item(ctx: Context, item_id: int) -> Item:
    stmt = (
        select(Item)
        .where(Item.id == item_id, Item.family_id == ctx.family.id)
        .options(selectinload(Item.units), selectinload(Item.photos), selectinload(Item.category))
    )
    item = ctx.db.scalar(stmt)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _path(ctx: Context):
    _, _, _, path = location_catalog(ctx.db, ctx.family.id)
    return path


def _set_quantity(ctx: Context, item: Item, quantity: int, location_id: int | None, use_sent_location: bool) -> tuple[int, int] | None:
    active = sorted((unit for unit in item.units if not unit.archived), key=lambda unit: unit.id)
    current = len(active)
    if quantity == current:
        return None
    if quantity > current:
        template = active[0] if active else None
        place = location_id if use_sent_location else (template.location_id if template else None)
        status = template.status if template and template.status in STATUSES else "available"
        _check_location(ctx, place)
        for _ in range(quantity - current):
            unit = ItemUnit(item_id=item.id, location_id=place, status=status)
            ctx.db.add(unit)
            item.units.append(unit)
    else:
        for unit in active[quantity:]:
            unit.archived = True
    return current, quantity


def _check_location(ctx: Context, location_id: int | None) -> None:
    if location_id is None:
        return
    _, _, locations, _ = location_catalog(ctx.db, ctx.family.id)
    if not any(location.id == location_id for location in locations):
        raise HTTPException(status_code=422, detail="Storage location is not in this family group")


def _apply_dimensions(payload) -> tuple[float | None, float | None]:
    width = payload.width
    length = payload.length
    if payload.dimension_text and (width is None or length is None):
        parsed = parse_dimension_pair(payload.dimension_text)
        if parsed is None:
            raise HTTPException(
                status_code=422,
                detail="Could not read those dimensions. Use a form such as 140 × 190, 140x190, 140/190, or 140 by 190.",
            )
        if width is None:
            width = parsed[0]
        if length is None:
            length = parsed[1]
    return width, length


def _snapshot(item: Item) -> dict:
    data = {}
    for key in TRACKED:
        value = getattr(item, key)
        data[key] = value
    return data


def _duplicates(ctx: Context, category_id: int, name: str, width, length, color) -> list[Item]:
    stmt = (
        select(Item)
        .where(Item.family_id == ctx.family.id, Item.archived.is_(False), Item.category_id == category_id)
        .options(selectinload(Item.category), selectinload(Item.units), selectinload(Item.photos))
    )
    found = []
    target = _norm(name)
    for item in ctx.db.scalars(stmt):
        same_name = target and target == _norm(item.name)
        same_size = (
            width is not None
            and length is not None
            and item.width is not None
            and item.length is not None
            and abs(item.width - width) <= 1
            and abs(item.length - length) <= 1
            and color
            and item.primary_color
            and color.lower() == item.primary_color.lower()
        )
        if same_name or same_size:
            found.append(item)
    return found


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


@router.get("/categories")
def categories(ctx: Context = Depends(get_context)):
    return [category_dict(category) for category in _visible_categories(ctx)]


@router.post("/categories", status_code=201)
def create_category(payload: CategoryIn, ctx: Context = Depends(require_role("admin"))):
    slug = re.sub(r"[^a-z0-9-]+", "-", payload.slug.lower()).strip("-")
    exists = ctx.db.scalar(
        select(Category).where(
            Category.slug == slug,
            or_(Category.family_id.is_(None), Category.family_id == ctx.family.id),
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="A category with this slug already exists")
    category = Category(
        family_id=ctx.family.id,
        slug=slug,
        name=payload.name.strip(),
        group_name=payload.group_name.strip() or "Custom",
        kind="textile",
        attribute_schema={"dimensions": payload.dimensions, "fields": payload.fields},
    )
    ctx.db.add(category)
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "category_created", {"slug": slug})
    ctx.db.commit()
    ctx.db.refresh(category)
    return category_dict(category)


@router.get("/rules")
def rules(ctx: Context = Depends(get_context)):
    rows = ctx.db.scalars(
        select(CompatibilityRule).where(CompatibilityRule.family_id == ctx.family.id).order_by(CompatibilityRule.id)
    ).all()
    return [
        {
            "id": row.id,
            "source_kind": row.source_kind,
            "target_slug": row.target_slug,
            "relationship": row.relationship,
            "enabled": row.enabled,
            "config": row.config or {},
        }
        for row in rows
    ]


class RuleIn(BaseModel):
    enabled: bool


@router.patch("/rules/{rule_id}")
def update_rule(rule_id: int, payload: RuleIn, ctx: Context = Depends(require_role("admin"))):
    rule = ctx.db.get(CompatibilityRule, rule_id)
    if rule is None or rule.family_id != ctx.family.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.enabled = payload.enabled
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "rule_updated", {"id": rule.id, "enabled": rule.enabled})
    ctx.db.commit()
    return {"id": rule.id, "enabled": rule.enabled}


@router.get("/items")
def list_items(
    ctx: Context = Depends(get_context),
    q: str = "",
    category_id: int | None = None,
    color: str = "",
    material: str = "",
    pattern: str = "",
    brand: str = "",
    status: str = "",
    seasonality: str = "",
    home_id: int | None = None,
    room_id: int | None = None,
    location_id: int | None = None,
    min_width: float | None = None,
    max_width: float | None = None,
    min_length: float | None = None,
    max_length: float | None = None,
    size: str = "",
    sort: str = "name",
    include_archived: bool = False,
):
    stmt = (
        select(Item)
        .where(Item.family_id == ctx.family.id)
        .options(selectinload(Item.units), selectinload(Item.photos), selectinload(Item.category))
    )
    if not include_archived:
        stmt = stmt.where(Item.archived.is_(False))
    items = list(ctx.db.scalars(stmt))
    homes, rooms, locations, path = location_catalog(ctx.db, ctx.family.id)
    loc_by = {location.id: location for location in locations}
    room_by = {room.id: room for room in rooms}
    descendant_ids = None
    if location_id is not None:
        descendant_ids = _descendants(location_id, locations)
    tokens = [token for token in re.split(r"\s+", q.strip().lower()) if token]
    size_pair = None
    if size.strip():
        size_pair = parse_dimension_pair(size)
        if size_pair is None:
            raise HTTPException(
                status_code=422,
                detail="Could not read that size. Use width × length, for example 220 × 200.",
            )

    def keep(item: Item) -> bool:
        if category_id and item.category_id != category_id:
            return False
        if color and color.lower() not in (item.primary_color or "").lower() and color.lower() not in " ".join(item.secondary_colors or []).lower():
            return False
        if material and material.lower() not in (item.material or "").lower():
            return False
        if pattern and pattern.lower() not in (item.pattern or "").lower():
            return False
        if brand and brand.lower() not in (item.brand or "").lower():
            return False
        if seasonality and seasonality.lower() not in (item.seasonality or "").lower():
            return False
        if min_width is not None and (item.width is None or item.width < min_width):
            return False
        if max_width is not None and (item.width is None or item.width > max_width):
            return False
        if min_length is not None and (item.length is None or item.length < min_length):
            return False
        if max_length is not None and (item.length is None or item.length > max_length):
            return False
        if size_pair is not None and not _matches_size(item.width, item.length, size_pair):
            return False
        units = [unit for unit in item.units if not unit.archived]
        if status and not any(unit.status == status for unit in units):
            return False
        if descendant_ids is not None and not any(unit.location_id in descendant_ids for unit in units):
            return False
        if home_id is not None or room_id is not None:
            if not any(_unit_in_place(unit, home_id, room_id, loc_by, room_by) for unit in units):
                return False
        if tokens:
            haystack = " ".join(
                [
                    item.name,
                    item.description,
                    item.brand,
                    item.primary_color,
                    " ".join(item.secondary_colors or []),
                    item.pattern,
                    item.material,
                    item.seasonality,
                    item.notes,
                    item.category.name if item.category else "",
                    item.category.slug if item.category else "",
                    " ".join(unit.status.replace("_", " ") for unit in units),
                    " ".join(path(unit.location_id) for unit in units),
                ]
            ).lower()
            if not all(token in haystack for token in tokens):
                return False
        return True

    filtered = [item for item in items if keep(item)]
    filtered.sort(key=lambda item: _sort_key(item, sort, path))
    return [item_dict(item, path) for item in filtered]


def _close_cm(left: float | None, right: float) -> bool:
    return left is not None and abs(left - right) <= 1


def _matches_size(width: float | None, length: float | None, pair: tuple[float, float]) -> bool:
    """Match width × length, and the same pair written the other way around."""
    first, second = pair
    straight = _close_cm(width, first) and _close_cm(length, second)
    rotated = _close_cm(width, second) and _close_cm(length, first)
    return straight or rotated


def _descendants(location_id: int, locations) -> set[int]:
    children = {}
    for location in locations:
        children.setdefault(location.parent_id, []).append(location.id)
    found = set()
    stack = [location_id]
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(children.get(current, []))
    return found


def _unit_in_place(unit, home_id, room_id, loc_by, room_by) -> bool:
    location = loc_by.get(unit.location_id)
    if location is None:
        return False
    if room_id is not None and location.room_id != room_id:
        return False
    if home_id is not None:
        room = room_by.get(location.room_id)
        if room is None or room.home_id != home_id:
            return False
    return True


def _sort_key(item: Item, sort: str, path):
    units = [unit for unit in item.units if not unit.archived]
    if sort == "category":
        return (item.category.name if item.category else "", item.name.lower())
    if sort == "width":
        return (item.width is None, item.width or 0, item.name.lower())
    if sort == "created":
        return (item.created_at is None, -(item.created_at.timestamp() if item.created_at else 0))
    if sort == "location":
        return (path(units[0].location_id) if units else "", item.name.lower())
    return (item.name.lower(),)


@router.post("/items", status_code=201)
def create_item(payload: ItemIn, ctx: Context = Depends(require_role("editor"))):
    if payload.unit_status not in STATUSES:
        raise HTTPException(status_code=422, detail="Unknown status")
    category = _category_or_404(ctx, payload.category_id)
    width, length = _apply_dimensions(payload)
    _check_location(ctx, payload.location_id)
    dupes = _duplicates(ctx, category.id, payload.name, width, length, payload.primary_color)
    if dupes and not payload.acknowledge_duplicates:
        path = _path(ctx)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A similar item already exists. Confirm if you still want a new record.",
                "duplicates": [item_dict(item, path) for item in dupes],
            },
        )
    now = datetime.now(timezone.utc)
    item = Item(
        family_id=ctx.family.id,
        category_id=category.id,
        name=payload.name.strip(),
        description=payload.description,
        brand=payload.brand,
        primary_color=payload.primary_color.strip().lower(),
        secondary_colors=[color.strip().lower() for color in payload.secondary_colors if color.strip()],
        pattern=payload.pattern.strip().lower(),
        texture=payload.texture,
        material=payload.material.strip().lower(),
        seasonality=payload.seasonality.strip().lower(),
        notes=payload.notes,
        width=width,
        length=length,
        height=payload.height,
        diameter=payload.diameter,
        attributes=payload.attributes or {},
        field_sources=payload.field_sources or {},
        version=1,
        created_at=now,
        updated_at=now,
    )
    ctx.db.add(item)
    ctx.db.flush()
    for _ in range(payload.quantity):
        ctx.db.add(ItemUnit(item_id=item.id, location_id=payload.location_id, status=payload.unit_status))
    add_history(ctx.db, ctx.family.id, ctx.user.id, "created", item.id, new={"name": item.name, "quantity": payload.quantity})
    notify_family(ctx.db, ctx.family.id, ctx.user.id, f"{ctx.user.full_name} added {item.name}.")
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.get("/items/{item_id}")
def get_item(item_id: int, ctx: Context = Depends(get_context)):
    return item_dict(_load_item(ctx, item_id), _path(ctx))


@router.patch("/items/{item_id}")
def update_item(item_id: int, payload: ItemUpdate, ctx: Context = Depends(require_role("editor"))):
    item = _load_item(ctx, item_id)
    if item.archived:
        raise HTTPException(status_code=409, detail="Restore the item before editing it")
    if payload.version != item.version:
        raise HTTPException(
            status_code=409,
            detail={"message": "Someone else saved this item. Review the latest version and try again.", "item": item_dict(item, _path(ctx))},
        )
    before = _snapshot(item)
    data = payload.model_dump(exclude_unset=True)
    data.pop("version", None)
    quantity = data.pop("quantity", None)
    place_for_new_units = data.pop("added_unit_location_id", None)
    place_was_sent = "added_unit_location_id" in payload.model_fields_set
    dimension_text = data.pop("dimension_text", None)
    if "category_id" in data and data["category_id"] is not None:
        _category_or_404(ctx, data["category_id"])
    if dimension_text:
        parsed = parse_dimension_pair(dimension_text)
        if parsed is None:
            raise HTTPException(status_code=422, detail="Could not read those dimensions.")
        if "width" not in data:
            data["width"] = parsed[0]
        if "length" not in data:
            data["length"] = parsed[1]
    for key, value in data.items():
        if key in {"primary_color", "pattern", "material", "seasonality"} and isinstance(value, str):
            value = value.strip().lower()
        if key == "secondary_colors" and value is not None:
            value = [color.strip().lower() for color in value if color.strip()]
        setattr(item, key, value)
    quantity_change = None
    if quantity is not None:
        quantity_change = _set_quantity(
            ctx,
            item,
            quantity,
            place_for_new_units if place_was_sent else None,
            place_was_sent,
        )
    item.version += 1
    item.updated_at = datetime.now(timezone.utc)
    after = _snapshot(item)
    changed = {key: {"from": before[key], "to": after[key]} for key in TRACKED if before.get(key) != after.get(key)}
    if changed:
        add_history(ctx.db, ctx.family.id, ctx.user.id, "updated", item.id, previous=before, new=after)
        notify_family(ctx.db, ctx.family.id, ctx.user.id, f"{ctx.user.full_name} updated {item.name}.")
    if quantity_change is not None:
        previous_quantity, next_quantity = quantity_change
        add_history(
            ctx.db,
            ctx.family.id,
            ctx.user.id,
            "quantity_changed",
            item.id,
            previous={"quantity": previous_quantity},
            new={"quantity": next_quantity},
        )
        notify_family(
            ctx.db,
            ctx.family.id,
            ctx.user.id,
            f"{ctx.user.full_name} changed the quantity of {item.name} to {next_quantity}.",
        )
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.post("/items/{item_id}/archive")
def archive_item(item_id: int, ctx: Context = Depends(require_role("editor"))):
    item = _load_item(ctx, item_id)
    item.archived = True
    item.version += 1
    item.updated_at = datetime.now(timezone.utc)
    add_history(ctx.db, ctx.family.id, ctx.user.id, "archived", item.id, new={"archived": True})
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.post("/items/{item_id}/restore")
def restore_item(item_id: int, ctx: Context = Depends(require_role("editor"))):
    item = _load_item(ctx, item_id)
    item.archived = False
    item.version += 1
    item.updated_at = datetime.now(timezone.utc)
    add_history(ctx.db, ctx.family.id, ctx.user.id, "restored", item.id, new={"archived": False})
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.get("/items/{item_id}/history")
def item_history(item_id: int, ctx: Context = Depends(get_context)):
    _load_item(ctx, item_id)
    from app.models import ItemHistory, User

    rows = ctx.db.scalars(
        select(ItemHistory).where(ItemHistory.item_id == item_id, ItemHistory.family_id == ctx.family.id).order_by(ItemHistory.created_at.desc())
    ).all()
    result = []
    for row in rows:
        actor = ctx.db.get(User, row.user_id) if row.user_id else None
        result.append(
            {
                "id": row.id,
                "action": row.action,
                "previous": row.previous_value,
                "new": row.new_value,
                "user_name": actor.full_name if actor else "Unknown",
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return result


@router.post("/items/{item_id}/units", status_code=201)
def add_units(item_id: int, payload: UnitIn, ctx: Context = Depends(require_role("editor"))):
    if payload.status not in STATUSES:
        raise HTTPException(status_code=422, detail="Unknown status")
    item = _load_item(ctx, item_id)
    _check_location(ctx, payload.location_id)
    for _ in range(payload.quantity):
        ctx.db.add(ItemUnit(item_id=item.id, location_id=payload.location_id, status=payload.status, notes=payload.notes))
    item.version += 1
    item.updated_at = datetime.now(timezone.utc)
    add_history(ctx.db, ctx.family.id, ctx.user.id, "quantity_changed", item.id, new={"added": payload.quantity, "status": payload.status})
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.patch("/units/{unit_id}")
def update_unit(unit_id: int, payload: UnitUpdate, ctx: Context = Depends(require_role("editor"))):
    unit = ctx.db.get(ItemUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    item = _load_item(ctx, unit.item_id)
    if payload.status is not None and payload.status not in STATUSES:
        raise HTTPException(status_code=422, detail="Unknown status")
    data = payload.model_dump(exclude_unset=True)
    clear_location = data.pop("clear_location", False)
    if "location_id" in data:
        _check_location(ctx, data["location_id"])
    previous = {"status": unit.status, "location_id": unit.location_id, "notes": unit.notes}
    if clear_location:
        unit.location_id = None
    for key, value in data.items():
        setattr(unit, key, value)
    item.version += 1
    item.updated_at = datetime.now(timezone.utc)
    action = "moved" if previous["location_id"] != unit.location_id else "status_changed"
    add_history(
        ctx.db,
        ctx.family.id,
        ctx.user.id,
        action,
        item.id,
        unit.id,
        previous=previous,
        new={"status": unit.status, "location_id": unit.location_id, "location": _path(ctx)(unit.location_id)},
    )
    notify_family(ctx.db, ctx.family.id, ctx.user.id, f"{ctx.user.full_name} updated a unit of {item.name}.")
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.post("/items/{item_id}/photos", status_code=201)
async def upload_photo(
    item_id: int,
    file: UploadFile = File(...),
    unit_id: int | None = None,
    ctx: Context = Depends(require_role("editor")),
):
    item = _load_item(ctx, item_id)
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Photographs must be 8 MB or smaller")
    try:
        full_path, thumb_path = save_photo(content, ctx.family.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    is_main = not any(photo.is_main for photo in item.photos)
    photo = Photo(item_id=item.id, unit_id=unit_id, path=full_path, thumb_path=thumb_path, is_main=is_main)
    ctx.db.add(photo)
    item.version += 1
    item.updated_at = datetime.now(timezone.utc)
    add_history(ctx.db, ctx.family.id, ctx.user.id, "photo_added", item.id, new={"main": is_main})
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.post("/photos/{photo_id}/main")
def make_main(photo_id: int, ctx: Context = Depends(require_role("editor"))):
    photo = ctx.db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photograph not found")
    item = _load_item(ctx, photo.item_id)
    for current in item.photos:
        current.is_main = current.id == photo.id
    item.version += 1
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.delete("/photos/{photo_id}")
def delete_photo(photo_id: int, ctx: Context = Depends(require_role("editor"))):
    photo = ctx.db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photograph not found")
    item = _load_item(ctx, photo.item_id)
    was_main = photo.is_main
    for relative in (photo.path, photo.thumb_path):
        try:
            absolute_path(relative).unlink(missing_ok=True)
        except ValueError:
            pass
    ctx.db.delete(photo)
    ctx.db.flush()
    if was_main:
        nxt = ctx.db.scalar(select(Photo).where(Photo.item_id == item.id).order_by(Photo.id))
        if nxt is not None:
            nxt.is_main = True
    item.version += 1
    add_history(ctx.db, ctx.family.id, ctx.user.id, "photo_removed", item.id)
    ctx.db.commit()
    return item_dict(_load_item(ctx, item.id), _path(ctx))


@router.get("/photos/{photo_id}/file")
def photo_file(
    photo_id: int,
    size: str = Query(default="full"),
    access_token: str | None = None,
    family_id: int | None = None,
    credentials=Depends(bearer),
    db=Depends(get_db),
):
    raw = credentials.credentials if credentials is not None else access_token
    if not raw:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        user_id = decode_token(raw)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    memberships = list(db.scalars(select(Membership).where(Membership.user_id == user.id)))
    chosen = next((row for row in memberships if family_id is None or row.family_id == family_id), None)
    if chosen is None:
        raise HTTPException(status_code=403, detail="No access to this family group")
    family = db.get(FamilyGroup, chosen.family_id)
    ctx = Context(user=user, family=family, membership=chosen, db=db)
    photo = ctx.db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photograph not found")
    _load_item(ctx, photo.item_id)
    relative = photo.thumb_path if size == "thumb" else photo.path
    try:
        path = absolute_path(relative)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Photograph file is missing") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photograph file is missing")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.post("/ai/suggest")
async def suggest(file: UploadFile = File(...), ctx: Context = Depends(require_role("editor"))):
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Photographs must be 8 MB or smaller")
    try:
        result = suggest_from_bytes(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "ai_suggest", {"fields": list(result["suggestions"].keys())})
    ctx.db.commit()
    return result


@router.get("/dashboard")
def dashboard(ctx: Context = Depends(get_context)):
    from app.models import ItemHistory

    stmt = (
        select(Item)
        .where(Item.family_id == ctx.family.id, Item.archived.is_(False))
        .options(selectinload(Item.units), selectinload(Item.photos), selectinload(Item.category))
    )
    items = list(ctx.db.scalars(stmt))
    _, _, _, path = location_catalog(ctx.db, ctx.family.id)
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in items:
        label = item.category.name if item.category else "Uncategorised"
        by_category[label] = by_category.get(label, 0) + 1
        for unit in item.units:
            if unit.archived:
                continue
            by_status[unit.status] = by_status.get(unit.status, 0) + 1
    recent_items = sorted(items, key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:6]
    history = ctx.db.scalars(
        select(ItemHistory).where(ItemHistory.family_id == ctx.family.id).order_by(ItemHistory.created_at.desc()).limit(8)
    ).all()
    return {
        "item_count": len(items),
        "unit_count": sum(by_status.values()),
        "by_category": [{"name": name, "count": count} for name, count in sorted(by_category.items())],
        "by_status": by_status,
        "recent_items": [item_dict(item, path) for item in recent_items],
        "recent_activity": [
            {"action": row.action, "item_id": row.item_id, "created_at": row.created_at.isoformat() if row.created_at else None}
            for row in history
        ],
    }


@router.get("/export/inventory.csv")
def export_csv(ctx: Context = Depends(get_context)):
    stmt = (
        select(Item)
        .where(Item.family_id == ctx.family.id, Item.archived.is_(False))
        .options(selectinload(Item.units), selectinload(Item.category))
    )
    items = list(ctx.db.scalars(stmt))
    _, _, _, path = location_catalog(ctx.db, ctx.family.id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["item_id", "unit_id", "name", "category", "width_cm", "length_cm", "height_cm", "diameter_cm",
         "color", "pattern", "material", "brand", "status", "location", "notes"]
    )
    for item in items:
        units = [unit for unit in item.units if not unit.archived] or [None]
        for unit in units:
            writer.writerow(
                [
                    item.id,
                    unit.id if unit else "",
                    item.name,
                    item.category.name if item.category else "",
                    item.width if item.width is not None else "",
                    item.length if item.length is not None else "",
                    item.height if item.height is not None else "",
                    item.diameter if item.diameter is not None else "",
                    item.primary_color,
                    item.pattern,
                    item.material,
                    item.brand,
                    unit.status if unit else "",
                    path(unit.location_id) if unit else "",
                    item.notes,
                ]
            )
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "export_csv", {"items": len(items)})
    ctx.db.commit()
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory.csv"},
    )
