from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Home, Room, StorageLocation


def location_catalog(db: Session, family_id: int):
    homes = list(db.scalars(select(Home).where(Home.family_id == family_id, Home.archived.is_(False))))
    home_ids = [home.id for home in homes]
    rooms = (
        list(db.scalars(select(Room).where(Room.home_id.in_(home_ids), Room.archived.is_(False))))
        if home_ids
        else []
    )
    locations = list(
        db.scalars(
            select(StorageLocation).where(
                StorageLocation.family_id == family_id,
                StorageLocation.archived.is_(False),
            )
        )
    )
    home_by = {home.id: home for home in homes}
    room_by = {room.id: room for room in rooms}
    loc_by = {loc.id: loc for loc in locations}

    def path(location_id: int | None) -> str:
        if location_id is None or location_id not in loc_by:
            return "No location"
        chain = []
        current = loc_by[location_id]
        seen = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            chain.append(current.name)
            current = loc_by.get(current.parent_id)
        chain.reverse()
        room = room_by.get(loc_by[location_id].room_id)
        home = home_by.get(room.home_id) if room else None
        prefix = [part.name for part in (home, room) if part is not None]
        return " / ".join(prefix + chain)

    return homes, rooms, locations, path
