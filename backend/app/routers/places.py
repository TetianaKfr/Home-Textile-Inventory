import secrets
from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.deps import Context, bearer, get_context, require_role
from app.models import FamilyGroup, Home, HouseholdObject, Item, ItemUnit, Membership, Room, StorageLocation, User
from app.security import decode_token
from app.serialize import object_dict
from app.services.activity import add_audit, add_history
from app.services.images import absolute_path, save_photo
from app.services.places import location_catalog

router = APIRouter(prefix="/api")


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class RoomIn(BaseModel):
    home_id: int
    name: str = Field(min_length=1, max_length=255)


class StorageIn(BaseModel):
    room_id: int
    parent_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    location_type: str = "storage"


class ObjectIn(BaseModel):
    kind: str
    name: str = Field(min_length=1, max_length=255)
    home_id: int | None = None
    room_id: int | None = None
    shape: str = ""
    width: float | None = None
    length: float | None = None
    height: float | None = None
    diameter: float | None = None
    depth: float | None = None
    attributes: dict = {}
    notes: str = ""


_OBJECT_MEASURES = ("width", "length", "height", "diameter", "depth")
_ATTRIBUTE_MEASURES = ("rail_width", "desired_length", "fullness", "overhang", "rail_to_floor", "panel_count")


def _reject_negative(payload: ObjectIn) -> None:
    for key in _OBJECT_MEASURES:
        value = getattr(payload, key)
        if value is not None and value < 0:
            raise HTTPException(status_code=422, detail="Length and height cannot be negative. Enter the measurement.")
    for key, value in (payload.attributes or {}).items():
        if key not in _ATTRIBUTE_MEASURES or value is None or value == "":
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number < 0:
            raise HTTPException(status_code=422, detail="Length and height cannot be negative. Enter the measurement.")


def _tree(ctx: Context) -> dict:
    homes, rooms, locations, path = location_catalog(ctx.db, ctx.family.id)
    room_groups: dict[int, list] = {}
    for room in rooms:
        room_groups.setdefault(room.home_id, []).append(room)
    loc_groups: dict[int, list] = {}
    for location in locations:
        loc_groups.setdefault(location.room_id, []).append(location)

    def nest(room_id: int, parent_id: int | None):
        nodes = []
        for location in loc_groups.get(room_id, []):
            if location.parent_id != parent_id:
                continue
            nodes.append(
                {
                    "id": location.id,
                    "name": location.name,
                    "location_type": location.location_type,
                    "path": path(location.id),
                    "children": nest(room_id, location.id),
                }
            )
        return nodes

    return {
        "homes": [
            {
                "id": home.id,
                "name": home.name,
                "has_photo": bool(home.photo_path),
                "rooms": [
                    {
                        "id": room.id,
                        "name": room.name,
                        "locations": nest(room.id, None),
                    }
                    for room in room_groups.get(home.id, [])
                ],
            }
            for home in homes
        ]
    }


@router.get("/locations/tree")
def tree(ctx: Context = Depends(get_context)):
    return _tree(ctx)


@router.post("/homes", status_code=201)
def create_home(payload: NameIn, ctx: Context = Depends(require_role("editor"))):
    home = Home(family_id=ctx.family.id, name=payload.name.strip())
    ctx.db.add(home)
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "home_created", {"name": home.name})
    ctx.db.commit()
    ctx.db.refresh(home)
    return {"id": home.id, "name": home.name}


@router.patch("/homes/{home_id}")
def rename_home(home_id: int, payload: NameIn, ctx: Context = Depends(require_role("editor"))):
    home = _home(ctx, home_id)
    home.name = payload.name.strip()
    ctx.db.commit()
    return {"id": home.id, "name": home.name}


@router.post("/homes/{home_id}/photo")
async def upload_home_photo(home_id: int, file: UploadFile = File(...), ctx: Context = Depends(require_role("editor"))):
    home = _home(ctx, home_id)
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Photographs must be 8 MB or smaller")
    try:
        full_path, thumb_path = save_photo(content, ctx.family.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    previous = [home.photo_path, home.thumb_path]
    home.photo_path = full_path
    home.thumb_path = thumb_path
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "home_photo_changed", {"home_id": home.id, "name": home.name})
    ctx.db.commit()
    _remove_photo_files(previous)
    return {"id": home.id, "has_photo": True}


@router.delete("/homes/{home_id}/photo")
def delete_home_photo(home_id: int, ctx: Context = Depends(require_role("editor"))):
    home = _home(ctx, home_id)
    previous = [home.photo_path, home.thumb_path]
    home.photo_path = None
    home.thumb_path = None
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "home_photo_removed", {"home_id": home.id, "name": home.name})
    ctx.db.commit()
    _remove_photo_files(previous)
    return {"id": home.id, "has_photo": False}


@router.get("/homes/{home_id}/photo")
def home_photo_file(
    home_id: int,
    size: str = Query(default="thumb"),
    access_token: str | None = None,
    family_id: int | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(get_db),
):
    raw = credentials.credentials if credentials is not None else access_token
    ctx = _context_from_token(db, raw, family_id)
    home = _home(ctx, home_id)
    relative = home.thumb_path if size == "thumb" else home.photo_path
    if not relative:
        raise HTTPException(status_code=404, detail="This home has no photograph")
    try:
        path = absolute_path(relative)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Photograph file is missing") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photograph file is missing")
    return Response(content=path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def _remove_photo_files(paths: list[str | None]) -> None:
    for relative in paths:
        if not relative:
            continue
        try:
            absolute_path(relative).unlink(missing_ok=True)
        except ValueError:
            pass


def _context_from_token(db, raw: str | None, family_id: int | None) -> Context:
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
    return Context(user=user, family=family, membership=chosen, db=db)


@router.delete("/homes/{home_id}")
def archive_home(home_id: int, ctx: Context = Depends(require_role("admin"))):
    home = _home(ctx, home_id)
    previous = [home.photo_path, home.thumb_path]
    home.archived = True
    home.photo_path = None
    home.thumb_path = None
    for room in ctx.db.scalars(select(Room).where(Room.home_id == home.id)).all():
        room.archived = True
    ctx.db.commit()
    _remove_photo_files(previous)
    return {"archived": home_id}


@router.post("/rooms", status_code=201)
def create_room(payload: RoomIn, ctx: Context = Depends(require_role("editor"))):
    _home(ctx, payload.home_id)
    room = Room(home_id=payload.home_id, name=payload.name.strip())
    ctx.db.add(room)
    ctx.db.commit()
    ctx.db.refresh(room)
    return {"id": room.id, "name": room.name, "home_id": room.home_id}


@router.delete("/rooms/{room_id}")
def archive_room(room_id: int, ctx: Context = Depends(require_role("editor"))):
    room = _room(ctx, room_id)
    locations = list(
        ctx.db.scalars(
            select(StorageLocation).where(
                StorageLocation.room_id == room.id,
                StorageLocation.archived.is_(False),
            )
        )
    )
    location_ids = [location.id for location in locations]
    if location_ids:
        in_use = ctx.db.scalar(
            select(ItemUnit.id)
            .join(Item)
            .where(
                ItemUnit.location_id.in_(location_ids),
                ItemUnit.archived.is_(False),
                Item.family_id == ctx.family.id,
                Item.archived.is_(False),
            )
        )
        if in_use:
            raise HTTPException(status_code=409, detail="Move the items out of this room before deleting it")
    for location in locations:
        location.archived = True
    for obj in ctx.db.scalars(
        select(HouseholdObject).where(HouseholdObject.room_id == room.id, HouseholdObject.archived.is_(False))
    ):
        obj.room_id = None
    room.archived = True
    ctx.db.commit()
    return {"archived": room_id}


@router.post("/storage", status_code=201)
def create_storage(payload: StorageIn, ctx: Context = Depends(require_role("editor"))):
    room = _room(ctx, payload.room_id)
    if payload.parent_id is not None:
        parent = _location(ctx, payload.parent_id)
        if parent.room_id != room.id:
            raise HTTPException(status_code=422, detail="A nested location must stay in the same room")
    location = StorageLocation(
        family_id=ctx.family.id,
        room_id=room.id,
        parent_id=payload.parent_id,
        name=payload.name.strip(),
        location_type=payload.location_type.strip() or "storage",
        qr_token=secrets.token_urlsafe(10),
    )
    ctx.db.add(location)
    ctx.db.commit()
    ctx.db.refresh(location)
    _, _, _, path = location_catalog(ctx.db, ctx.family.id)
    return {"id": location.id, "name": location.name, "path": path(location.id), "qr_token": location.qr_token}


@router.delete("/storage/{location_id}")
def archive_storage(location_id: int, ctx: Context = Depends(require_role("editor"))):
    location = _location(ctx, location_id)
    subtree = _subtree(ctx, location)
    location_ids = [node.id for node in subtree]
    in_use = ctx.db.scalar(
        select(ItemUnit.id).join(Item).where(
            ItemUnit.location_id.in_(location_ids),
            ItemUnit.archived.is_(False),
            Item.family_id == ctx.family.id,
            Item.archived.is_(False),
        )
    )
    if in_use:
        raise HTTPException(status_code=409, detail="Move the items out of this location before deleting it")
    for node in subtree:
        node.archived = True
    ctx.db.commit()
    return {"archived": location_id}


@router.get("/storage/{location_id}")
def storage_detail(location_id: int, ctx: Context = Depends(get_context)):
    location = _location(ctx, location_id)
    _, _, _, path = location_catalog(ctx.db, ctx.family.id)
    units = ctx.db.scalars(
        select(ItemUnit).join(Item).where(
            ItemUnit.location_id == location.id,
            ItemUnit.archived.is_(False),
            Item.family_id == ctx.family.id,
            Item.archived.is_(False),
        )
    ).all()
    items = []
    seen = set()
    for unit in units:
        if unit.item_id in seen:
            continue
        seen.add(unit.item_id)
        item = unit.item
        items.append(
            {
                "id": item.id,
                "name": item.name,
                "category": item.category.name if item.category else "",
                "quantity_here": sum(1 for candidate in units if candidate.item_id == item.id),
                "photo_id": next((photo.id for photo in item.photos if photo.is_main), None),
            }
        )
    return {"id": location.id, "name": location.name, "path": path(location.id), "type": location.location_type, "items": items}


@router.get("/storage/{location_id}/qr.png")
def storage_qr(location_id: int, ctx: Context = Depends(get_context)):
    location = _location(ctx, location_id)
    if location.location_type.strip().lower() != "box":
        raise HTTPException(status_code=404, detail="QR codes are only available for boxes")
    url = f"{get_settings().public_base_url}/#/locations/{location.id}"
    image = qrcode.make(url)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


def _check_object_place(ctx: Context, payload: ObjectIn) -> None:
    home = _home(ctx, payload.home_id) if payload.home_id is not None else None
    room = _room(ctx, payload.room_id) if payload.room_id is not None else None
    if room is not None and home is None:
        raise HTTPException(status_code=422, detail="Choose a home for this room")
    if room is not None and home is not None and room.home_id != home.id:
        raise HTTPException(status_code=422, detail="Choose a room from the selected home")


def _home(ctx: Context, home_id: int) -> Home:
    home = ctx.db.get(Home, home_id)
    if home is None or home.archived or home.family_id != ctx.family.id:
        raise HTTPException(status_code=404, detail="Home not found")
    return home


def _room(ctx: Context, room_id: int) -> Room:
    room = ctx.db.get(Room, room_id)
    if room is None or room.archived or room.home.family_id != ctx.family.id:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


def _location(ctx: Context, location_id: int) -> StorageLocation:
    location = ctx.db.get(StorageLocation, location_id)
    if location is None or location.archived or location.family_id != ctx.family.id:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


def _subtree(ctx: Context, root: StorageLocation) -> list[StorageLocation]:
    found: list[StorageLocation] = []
    pending = [root]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current.id in seen:
            continue
        seen.add(current.id)
        found.append(current)
        pending.extend(
            ctx.db.scalars(
                select(StorageLocation).where(
                    StorageLocation.parent_id == current.id,
                    StorageLocation.family_id == ctx.family.id,
                    StorageLocation.archived.is_(False),
                )
            ).all()
        )
    return found


@router.get("/objects")
def list_objects(kind: str = "", ctx: Context = Depends(get_context)):
    stmt = select(HouseholdObject).where(HouseholdObject.family_id == ctx.family.id, HouseholdObject.archived.is_(False))
    if kind:
        stmt = stmt.where(HouseholdObject.kind == kind)
    homes, rooms, _, _ = location_catalog(ctx.db, ctx.family.id)
    home_names = {home.id: home.name for home in homes}
    room_names = {room.id: room.name for room in rooms}
    rows = [
        object_dict(obj, home_names.get(obj.home_id, ""), room_names.get(obj.room_id, ""))
        for obj in ctx.db.scalars(stmt)
    ]
    rows.sort(key=_object_order)
    return rows


def _object_order(row: dict) -> tuple:
    def place(value: str) -> tuple[bool, str]:
        text = (value or "").casefold()
        return (not text, text)

    return (
        *place(row.get("home_name") or ""),
        *place(row.get("room_name") or ""),
        (row.get("name") or "").casefold(),
        row.get("kind") or "",
    )


@router.post("/objects", status_code=201)
def create_object(payload: ObjectIn, ctx: Context = Depends(require_role("editor"))):
    if payload.kind not in {"bed", "mattress", "table", "window"}:
        raise HTTPException(status_code=422, detail="Unknown object type")
    _reject_negative(payload)
    _check_object_place(ctx, payload)
    data = payload.model_dump()
    data["attributes"] = {
        key: value for key, value in (data.get("attributes") or {}).items() if value is not None and value != ""
    }
    obj = HouseholdObject(family_id=ctx.family.id, **data)
    ctx.db.add(obj)
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "object_created", {"kind": payload.kind, "name": payload.name})
    ctx.db.commit()
    ctx.db.refresh(obj)
    return object_dict(obj)


@router.patch("/objects/{object_id}")
def update_object(object_id: int, payload: ObjectIn, ctx: Context = Depends(require_role("editor"))):
    if payload.kind not in {"bed", "mattress", "table", "window"}:
        raise HTTPException(status_code=422, detail="Unknown object type")
    _reject_negative(payload)
    _check_object_place(ctx, payload)
    obj = _object(ctx, object_id)
    data = payload.model_dump()
    incoming = data.pop("attributes") or {}
    merged = dict(obj.attributes or {})
    for key, value in incoming.items():
        if value is None or value == "":
            merged.pop(key, None)
        else:
            merged[key] = value
    for key, value in data.items():
        setattr(obj, key, value)
    obj.attributes = merged
    ctx.db.commit()
    return object_dict(obj)


@router.delete("/objects/{object_id}")
def archive_object(object_id: int, ctx: Context = Depends(require_role("editor"))):
    obj = _object(ctx, object_id)
    obj.archived = True
    ctx.db.commit()
    return {"archived": object_id}


def _object(ctx: Context, object_id: int) -> HouseholdObject:
    obj = ctx.db.get(HouseholdObject, object_id)
    if obj is None or obj.archived or obj.family_id != ctx.family.id:
        raise HTTPException(status_code=404, detail="Object not found")
    return obj
