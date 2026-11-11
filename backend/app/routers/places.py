import secrets
from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import get_settings
from app.deps import Context, get_context, require_role
from app.models import Home, HouseholdObject, Item, ItemUnit, Room, StorageLocation
from app.serialize import object_dict
from app.services.activity import add_audit, add_history
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


@router.delete("/homes/{home_id}")
def archive_home(home_id: int, ctx: Context = Depends(require_role("admin"))):
    home = _home(ctx, home_id)
    home.archived = True
    for room in ctx.db.scalars(select(Room).where(Room.home_id == home.id)).all():
        room.archived = True
    ctx.db.commit()
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
def archive_room(room_id: int, ctx: Context = Depends(require_role("admin"))):
    room = _room(ctx, room_id)
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
def archive_storage(location_id: int, ctx: Context = Depends(require_role("admin"))):
    location = _location(ctx, location_id)
    in_use = ctx.db.scalar(
        select(ItemUnit.id).join(Item).where(
            ItemUnit.location_id == location.id,
            ItemUnit.archived.is_(False),
            Item.family_id == ctx.family.id,
            Item.archived.is_(False),
        )
    )
    if in_use:
        raise HTTPException(status_code=409, detail="Move the items out of this location before archiving it")
    location.archived = True
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
    url = f"{get_settings().public_base_url}/#/locations/{location.id}"
    image = qrcode.make(url)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


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


@router.get("/objects")
def list_objects(kind: str = "", ctx: Context = Depends(get_context)):
    stmt = select(HouseholdObject).where(HouseholdObject.family_id == ctx.family.id, HouseholdObject.archived.is_(False))
    if kind:
        stmt = stmt.where(HouseholdObject.kind == kind)
    homes, rooms, _, _ = location_catalog(ctx.db, ctx.family.id)
    home_names = {home.id: home.name for home in homes}
    room_names = {room.id: room.name for room in rooms}
    return [
        object_dict(obj, home_names.get(obj.home_id, ""), room_names.get(obj.room_id, ""))
        for obj in ctx.db.scalars(stmt.order_by(HouseholdObject.name))
    ]


@router.post("/objects", status_code=201)
def create_object(payload: ObjectIn, ctx: Context = Depends(require_role("editor"))):
    if payload.kind not in {"bed", "mattress", "table", "window"}:
        raise HTTPException(status_code=422, detail="Unknown object type")
    if payload.home_id is not None:
        _home(ctx, payload.home_id)
    if payload.room_id is not None:
        _room(ctx, payload.room_id)
    obj = HouseholdObject(family_id=ctx.family.id, **payload.model_dump())
    ctx.db.add(obj)
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "object_created", {"kind": payload.kind, "name": payload.name})
    ctx.db.commit()
    ctx.db.refresh(obj)
    return object_dict(obj)


@router.patch("/objects/{object_id}")
def update_object(object_id: int, payload: ObjectIn, ctx: Context = Depends(require_role("editor"))):
    obj = _object(ctx, object_id)
    for key, value in payload.model_dump().items():
        setattr(obj, key, value)
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
