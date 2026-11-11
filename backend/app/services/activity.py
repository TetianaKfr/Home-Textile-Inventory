from sqlalchemy.orm import Session

from app.models import AuditLog, ItemHistory, Membership, Notification


def add_history(
    db: Session,
    family_id: int,
    user_id: int | None,
    action: str,
    item_id: int | None = None,
    unit_id: int | None = None,
    previous: dict | None = None,
    new: dict | None = None,
) -> None:
    db.add(
        ItemHistory(
            family_id=family_id,
            item_id=item_id,
            unit_id=unit_id,
            action=action,
            previous_value=previous,
            new_value=new,
            user_id=user_id,
        )
    )


def add_audit(db: Session, family_id: int | None, user_id: int | None, action: str, detail: dict | None = None) -> None:
    db.add(AuditLog(family_id=family_id, user_id=user_id, action=action, detail=detail or {}))


def notify_family(db: Session, family_id: int, actor_id: int | None, message: str, kind: str = "activity") -> None:
    members = db.query(Membership).filter(Membership.family_id == family_id).all()
    for member in members:
        if actor_id is not None and member.user_id == actor_id:
            continue
        if kind != "invitation" and not member.user.notify_changes:
            continue
        db.add(Notification(family_id=family_id, user_id=member.user_id, message=message, kind=kind))
