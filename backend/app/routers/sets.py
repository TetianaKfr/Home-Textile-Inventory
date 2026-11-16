from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import Context, get_context, require_role
from app.models import HouseholdObject, Item, SavedSet, SetLink
from app.serialize import item_dict
from app.services.activity import add_history
from app.services.matching import build_match
from app.services.places import location_catalog

router = APIRouter(prefix="/api")


class MatchIn(BaseModel):
    object_id: int
    table_overhang_cm: float | None = None
    sheet_side_overhang_cm: float | None = None
    sheet_head_overhang_cm: float | None = None
    sheet_foot_overhang_cm: float | None = None
    size_tolerance_cm: float | None = None
    duvet_tolerance_cm: float | None = None
    pillow_allowance_cm: float | None = None
    curtain_fullness: float | None = None
    home_id: int | None = None


class SetIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    object_id: int | None = None
    notes: str = ""
    item_ids: list[int] = []
    roles: dict[str, str] = {}


@router.post("/matching")
def match(payload: MatchIn, ctx: Context = Depends(get_context)):
    obj = ctx.db.get(HouseholdObject, payload.object_id)
    if obj is None or obj.archived or obj.family_id != ctx.family.id:
        raise HTTPException(status_code=404, detail="Object not found")
    if payload.home_id is not None:
        homes, _, _, _ = location_catalog(ctx.db, ctx.family.id)
        if not any(home.id == payload.home_id for home in homes):
            raise HTTPException(status_code=404, detail="Home not found")
    overrides = payload.model_dump(exclude={"object_id", "home_id"}, exclude_none=True)
    preferences = {**(ctx.family.preferences or {})}
    return build_match(ctx.db, ctx.family.id, obj, overrides, preferences, payload.home_id)


@router.get("/sets")
def list_sets(ctx: Context = Depends(get_context)):
    stmt = (
        select(SavedSet)
        .where(SavedSet.family_id == ctx.family.id, SavedSet.archived.is_(False))
        .options(selectinload(SavedSet.links).selectinload(SetLink.item).selectinload(Item.units), selectinload(SavedSet.links).selectinload(SetLink.item).selectinload(Item.category), selectinload(SavedSet.links).selectinload(SetLink.item).selectinload(Item.photos), selectinload(SavedSet.household_object))
        .order_by(SavedSet.updated_at.desc())
    )
    _, _, _, path = location_catalog(ctx.db, ctx.family.id)
    return [_set_dict(row, path) for row in ctx.db.scalars(stmt)]


@router.post("/sets", status_code=201)
def create_set(payload: SetIn, ctx: Context = Depends(require_role("editor"))):
    if payload.object_id is not None:
        obj = ctx.db.get(HouseholdObject, payload.object_id)
        if obj is None or obj.family_id != ctx.family.id:
            raise HTTPException(status_code=422, detail="The related object is not in this family group")
    saved = SavedSet(family_id=ctx.family.id, name=payload.name.strip(), object_id=payload.object_id, notes=payload.notes)
    ctx.db.add(saved)
    ctx.db.flush()
    for item_id in payload.item_ids:
        item = ctx.db.get(Item, item_id)
        if item is None or item.family_id != ctx.family.id:
            raise HTTPException(status_code=422, detail=f"Item {item_id} is not in this family group")
        ctx.db.add(SetLink(set_id=saved.id, item_id=item.id, role=payload.roles.get(str(item_id), "")))
        add_history(ctx.db, ctx.family.id, ctx.user.id, "added_to_set", item.id, new={"set": saved.name})
    ctx.db.commit()
    return {"id": saved.id, "name": saved.name}


@router.delete("/sets/{set_id}")
def archive_set(set_id: int, ctx: Context = Depends(require_role("editor"))):
    saved = ctx.db.get(SavedSet, set_id)
    if saved is None or saved.family_id != ctx.family.id:
        raise HTTPException(status_code=404, detail="Saved set not found")
    saved.archived = True
    ctx.db.commit()
    return {"archived": set_id}


def _set_dict(saved: SavedSet, path) -> dict:
    items = []
    needs_attention = False
    for link in saved.links:
        item = link.item
        if item is None or item.archived:
            needs_attention = True
            items.append({"item_id": link.item_id, "name": "Missing item", "role": link.role, "missing": True})
            continue
        active = [unit for unit in item.units if not unit.archived and unit.status not in {"archived", "damaged"}]
        if not active:
            needs_attention = True
        payload = item_dict(item, path)
        payload["role"] = link.role
        payload["needs_attention"] = not active
        items.append(payload)
    return {
        "id": saved.id,
        "name": saved.name,
        "notes": saved.notes,
        "object_id": saved.object_id,
        "object_name": saved.household_object.name if saved.household_object else "",
        "needs_attention": needs_attention,
        "items": items,
        "created_at": saved.created_at.isoformat() if saved.created_at else None,
        "updated_at": saved.updated_at.isoformat() if saved.updated_at else None,
    }
