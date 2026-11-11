import secrets
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.catalog import COLORS, DEFAULT_PREFERENCES, MATERIALS, PATTERNS, ROLES, SEASONS, STATUSES
from app.deps import Context, get_context, get_current_user, require_role
from app.models import FamilyGroup, Invitation, Membership, Notification, User
from app.security import create_token, hash_password, verify_password
from app.serialize import user_brief
from app.services.activity import add_audit, notify_family

router = APIRouter(prefix="/api")


def get_db_plain():
    from app.database import get_db

    yield from get_db()

RULE_TEMPLATES = [
    ("bed", "fitted-sheet", "Fitted sheet for a mattress"),
    ("bed", "bed-sheet", "Flat sheet for a mattress"),
    ("bed", "mattress-protector", "Mattress protector"),
    ("duvet", "duvet-cover", "Duvet cover for a duvet"),
    ("pillow", "pillowcase", "Pillowcase for a pillow"),
    ("pillow", "pillow-protector", "Pillow protector"),
    ("table", "tablecloth", "Tablecloth for a table"),
    ("window", "curtain", "Curtains for a window"),
    ("window", "drape", "Drapes for a window"),
    ("window", "sheer-curtain", "Sheer curtains for a window"),
]


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    family_name: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _clean_email(value)


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _clean_email(value)


class InviteIn(BaseModel):
    email: str
    role: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _clean_email(value)


def _clean_email(value: str) -> str:
    email = value.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("Enter a valid email address")
    return email


class AcceptIn(BaseModel):
    token: str


class RoleIn(BaseModel):
    role: str


class PreferencesIn(BaseModel):
    table_overhang_cm: float | None = None
    sheet_side_overhang_cm: float | None = None
    sheet_head_overhang_cm: float | None = None
    sheet_foot_overhang_cm: float | None = None
    size_tolerance_cm: float | None = None
    duvet_tolerance_cm: float | None = None
    pillow_allowance_cm: float | None = None
    curtain_fullness: float | None = None


class NotifyIn(BaseModel):
    notify_changes: bool


def _memberships(db, user: User) -> list[dict]:
    rows = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    result = []
    for row in rows:
        family = db.get(FamilyGroup, row.family_id)
        result.append({"family_id": row.family_id, "family_name": family.name if family else "", "role": row.role})
    return result


def _token_response(db, user: User) -> dict:
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": user_brief(user), "memberships": _memberships(db, user)}


def copy_rules(db, family_id: int) -> None:
    from app.models import CompatibilityRule

    for source, target, label in RULE_TEMPLATES:
        db.add(
            CompatibilityRule(
                family_id=family_id,
                source_kind=source,
                target_slug=target,
                relationship=label,
                config={},
                enabled=True,
            )
        )


@router.get("/meta")
def meta():
    return {
        "colors": COLORS,
        "patterns": PATTERNS,
        "materials": MATERIALS,
        "seasons": SEASONS,
        "statuses": STATUSES,
        "roles": ROLES,
        "object_kinds": ["bed", "mattress", "table", "window"],
    }


@router.post("/auth/register", status_code=201)
def register(payload: RegisterIn, db=Depends(get_db_plain)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    family = FamilyGroup(name=payload.family_name.strip(), preferences=dict(DEFAULT_PREFERENCES))
    db.add(family)
    db.flush()
    db.add(Membership(family_id=family.id, user_id=user.id, role="admin"))
    copy_rules(db, family.id)
    add_audit(db, family.id, user.id, "family_created", {"name": family.name})
    db.commit()
    return _token_response(db, user)


@router.post("/auth/login")
def login(payload: LoginIn, db=Depends(get_db_plain)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return _token_response(db, user)


@router.get("/auth/me")
def me(user: User = Depends(get_current_user), db=Depends(get_db_plain)):
    return {"user": user_brief(user), "memberships": _memberships(db, user)}


@router.patch("/auth/me")
def update_me(payload: NotifyIn, user: User = Depends(get_current_user), db=Depends(get_db_plain)):
    user.notify_changes = payload.notify_changes
    db.commit()
    return user_brief(user)


@router.get("/family")
def family(ctx: Context = Depends(get_context)):
    members = ctx.db.scalars(select(Membership).where(Membership.family_id == ctx.family.id)).all()
    invitations = ctx.db.scalars(
        select(Invitation).where(Invitation.family_id == ctx.family.id, Invitation.status == "pending")
    ).all()
    return {
        "id": ctx.family.id,
        "name": ctx.family.name,
        "role": ctx.membership.role,
        "preferences": {**DEFAULT_PREFERENCES, **(ctx.family.preferences or {})},
        "members": [
            {**user_brief(member.user), "role": member.role}
            for member in members
        ],
        "invitations": [
            {"id": item.id, "email": item.email, "role": item.role, "token": item.token, "created_at": item.created_at.isoformat()}
            for item in invitations
        ],
    }


@router.post("/family/invitations", status_code=201)
def invite(payload: InviteIn, ctx: Context = Depends(require_role("admin"))):
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail="Unknown role")
    email = payload.email.lower()
    token = secrets.token_urlsafe(18)
    row = Invitation(
        family_id=ctx.family.id,
        email=email,
        role=payload.role,
        token=token,
        invited_by=ctx.user.id,
    )
    ctx.db.add(row)
    existing = ctx.db.scalar(select(User).where(User.email == email))
    if existing is not None:
        ctx.db.add(
            Notification(
                family_id=ctx.family.id,
                user_id=existing.id,
                message=f"{ctx.user.full_name} invited you to join {ctx.family.name} as {payload.role}.",
                kind="invitation",
            )
        )
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "invitation_created", {"email": email, "role": payload.role})
    ctx.db.commit()
    return {"token": token, "email": email, "role": payload.role}


@router.get("/invitations/{token}")
def preview_invitation(token: str, db=Depends(get_db_plain)):
    row = db.scalar(select(Invitation).where(Invitation.token == token, Invitation.status == "pending"))
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    family = db.get(FamilyGroup, row.family_id)
    return {"email": row.email, "role": row.role, "family_name": family.name if family else ""}


@router.post("/family/invitations/accept")
def accept_invitation(payload: AcceptIn, user: User = Depends(get_current_user), db=Depends(get_db_plain)):
    row = db.scalar(select(Invitation).where(Invitation.token == payload.token, Invitation.status == "pending"))
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if user.email != row.email:
        raise HTTPException(status_code=403, detail="Sign in with the invited email address to accept")
    existing = db.scalar(select(Membership).where(Membership.family_id == row.family_id, Membership.user_id == user.id))
    if existing is None:
        db.add(Membership(family_id=row.family_id, user_id=user.id, role=row.role))
    row.status = "accepted"
    add_audit(db, row.family_id, user.id, "invitation_accepted", {"email": user.email, "role": row.role})
    notify_family(db, row.family_id, user.id, f"{user.full_name} joined the family group.")
    db.commit()
    return _token_response(db, user)


@router.patch("/family/members/{user_id}")
def change_role(user_id: int, payload: RoleIn, ctx: Context = Depends(require_role("admin"))):
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail="Unknown role")
    member = ctx.db.scalar(
        select(Membership).where(Membership.family_id == ctx.family.id, Membership.user_id == user_id)
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "admin" and payload.role != "admin":
        _ensure_other_admin(ctx, user_id)
    previous = member.role
    member.role = payload.role
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "role_changed", {"user_id": user_id, "from": previous, "to": payload.role})
    ctx.db.commit()
    return {"user_id": user_id, "role": payload.role}


@router.delete("/family/members/{user_id}")
def remove_member(user_id: int, ctx: Context = Depends(require_role("admin"))):
    member = ctx.db.scalar(
        select(Membership).where(Membership.family_id == ctx.family.id, Membership.user_id == user_id)
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "admin":
        _ensure_other_admin(ctx, user_id)
    ctx.db.delete(member)
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "member_removed", {"user_id": user_id})
    ctx.db.commit()
    return {"removed": user_id}


def _ensure_other_admin(ctx: Context, user_id: int) -> None:
    admins = ctx.db.scalars(
        select(Membership).where(Membership.family_id == ctx.family.id, Membership.role == "admin")
    ).all()
    if len([admin for admin in admins if admin.user_id != user_id]) < 1:
        raise HTTPException(status_code=409, detail="The family group needs at least one administrator")


@router.patch("/family/preferences")
def update_preferences(payload: PreferencesIn, ctx: Context = Depends(require_role("admin"))):
    current = {**DEFAULT_PREFERENCES, **(ctx.family.preferences or {})}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if value <= 0:
            raise HTTPException(status_code=422, detail=f"{key} must be greater than zero")
        current[key] = value
    ctx.family.preferences = current
    add_audit(ctx.db, ctx.family.id, ctx.user.id, "preferences_updated", current)
    ctx.db.commit()
    return current


@router.get("/notifications")
def notifications(ctx: Context = Depends(get_context)):
    rows = ctx.db.scalars(
        select(Notification)
        .where(Notification.user_id == ctx.user.id, Notification.family_id == ctx.family.id)
        .order_by(Notification.created_at.desc())
        .limit(40)
    ).all()
    return [
        {
            "id": row.id,
            "message": row.message,
            "kind": row.kind,
            "read": row.read,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/notifications/read")
def read_notifications(ctx: Context = Depends(get_context)):
    rows = ctx.db.scalars(
        select(Notification).where(
            Notification.user_id == ctx.user.id,
            Notification.family_id == ctx.family.id,
            Notification.read.is_(False),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.read = True
        row.created_at = row.created_at or now
    ctx.db.commit()
    return {"updated": len(rows)}
