from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import ROLE_RANK
from app.database import get_db
from app.models import FamilyGroup, Membership, User
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class Context:
    user: User
    family: FamilyGroup
    membership: Membership
    db: Session


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        user_id = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_context(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_family_id: int | None = Header(default=None),
) -> Context:
    stmt = select(Membership).where(Membership.user_id == user.id)
    memberships = list(db.scalars(stmt))
    if not memberships:
        raise HTTPException(status_code=403, detail="You do not belong to a family group")
    chosen = None
    if x_family_id is not None:
        chosen = next((m for m in memberships if m.family_id == x_family_id), None)
        if chosen is None:
            raise HTTPException(status_code=403, detail="No access to this family group")
    else:
        chosen = memberships[0]
    family = db.get(FamilyGroup, chosen.family_id)
    return Context(user=user, family=family, membership=chosen, db=db)


def require_role(min_role: str):
    def dependency(ctx: Context = Depends(get_context)) -> Context:
        if ROLE_RANK[ctx.membership.role] < ROLE_RANK[min_role]:
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        return ctx

    return dependency
