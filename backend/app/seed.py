import secrets
from io import BytesIO

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.catalog import DEFAULT_PREFERENCES, system_categories
from app.config import get_settings
from app.models import (
    Category,
    FamilyGroup,
    Home,
    HouseholdObject,
    Item,
    ItemUnit,
    Membership,
    Photo,
    Room,
    StorageLocation,
    User,
)
from app.routers.auth import copy_rules
from app.security import hash_password
from app.services.images import save_photo

DEMO_PASSWORD = "Demo1234!"


def seed(db) -> None:
    if not db.scalar(select(Category).where(Category.family_id.is_(None)).limit(1)):
        for spec in system_categories():
            db.add(Category(family_id=None, **spec))
        db.commit()
    if not get_settings().seed_demo:
        return
    if db.scalar(select(User).where(User.email == "demo@home-textile.local")):
        return

    password = hash_password(DEMO_PASSWORD)
    admin = User(email="demo@home-textile.local", full_name="Alex Martin", password_hash=password)
    editor = User(email="editor@home-textile.local", full_name="Camille Martin", password_hash=password)
    viewer = User(email="viewer@home-textile.local", full_name="Noah Martin", password_hash=password)
    db.add_all([admin, editor, viewer])
    db.flush()
    family = FamilyGroup(name="Martin household", preferences=dict(DEFAULT_PREFERENCES))
    db.add(family)
    db.flush()
    db.add_all(
        [
            Membership(family_id=family.id, user_id=admin.id, role="admin"),
            Membership(family_id=family.id, user_id=editor.id, role="editor"),
            Membership(family_id=family.id, user_id=viewer.id, role="viewer"),
        ]
    )
    copy_rules(db, family.id)

    home = Home(family_id=family.id, name="Apartment Lyon")
    db.add(home)
    db.flush()
    bedroom = Room(home_id=home.id, name="Bedroom")
    bathroom = Room(home_id=home.id, name="Bathroom")
    dining = Room(home_id=home.id, name="Dining room")
    living = Room(home_id=home.id, name="Living room")
    db.add_all([bedroom, bathroom, dining, living])
    db.flush()

    wardrobe = _location(db, family.id, bedroom.id, None, "Wardrobe", "cupboard")
    shelf = _location(db, family.id, bedroom.id, wardrobe.id, "Shelf 1", "shelf")
    box = _location(db, family.id, bedroom.id, wardrobe.id, "Box 4", "box")
    cabinet = _location(db, family.id, bathroom.id, None, "Cabinet", "cupboard")
    drawer = _location(db, family.id, bathroom.id, cabinet.id, "Drawer 1", "drawer")
    sideboard = _location(db, family.id, dining.id, None, "Sideboard", "cupboard")

    cats = {row.slug: row for row in db.scalars(select(Category).where(Category.family_id.is_(None)))}

    def add(slug, name, color, rgb, width, length, location, status="available", quantity=1, **extra):
        item = Item(
            family_id=family.id,
            category_id=cats[slug].id,
            name=name,
            primary_color=color,
            pattern=extra.pop("pattern", "plain"),
            material=extra.pop("material", "cotton"),
            seasonality=extra.pop("seasonality", ""),
            brand=extra.pop("brand", ""),
            width=width,
            length=length,
            height=extra.pop("height", None),
            diameter=extra.pop("diameter", None),
            attributes=extra.pop("attributes", {}),
            field_sources={},
            notes=extra.pop("notes", ""),
        )
        db.add(item)
        db.flush()
        full, thumb = _swatch(family.id, rgb, name)
        db.add(Photo(item_id=item.id, path=full, thumb_path=thumb, is_main=True))
        units = extra.pop("units", None)
        if units:
            for unit_location, unit_status in units:
                db.add(ItemUnit(item_id=item.id, location_id=getattr(unit_location, "id", unit_location), status=unit_status))
        else:
            for _ in range(quantity):
                db.add(ItemUnit(item_id=item.id, location_id=getattr(location, "id", None), status=status))
        return item

    add("fitted-sheet", "White fitted sheet", "white", (244, 244, 242), 140, 190, shelf, attributes={"sheet_type": "fitted", "mattress_depth": 25, "elastic": "elastic all around"})
    add("bed-sheet", "Ivory flat sheet", "ivory", (248, 242, 220), 200, 260, shelf, attributes={"sheet_type": "flat"})
    add("fitted-sheet", "Small grey fitted sheet", "grey", (170, 170, 170), 90, 190, box, attributes={"sheet_type": "fitted", "mattress_depth": 10}, notes="Too small for the main bed.")
    add("duvet", "Winter duvet", "white", (236, 236, 236), 220, 200, shelf, material="down", seasonality="winter", attributes={"season": "winter", "filling": "down", "warmth": "warm", "thickness": 8})
    add("duvet-cover", "Blue floral duvet cover", "blue", (70, 110, 170), 220, 200, shelf, pattern="floral", attributes={"closure": "buttons", "seasonality_hint": "all-season"})
    add("duvet-cover", "Navy duvet cover", "navy", (32, 48, 92), 215, 198, box, pattern="plain", attributes={"closure": "zipper"})
    add("pillow", "Cream square pillow", "cream", (245, 236, 210), 60, 60, shelf, quantity=2, height=12, attributes={"filling": "down", "firmness": "medium", "shape": "square"})
    add("pillowcase", "White pillowcase", "white", (250, 250, 248), 65, 65, shelf, quantity=2, attributes={"closure": "envelope"})
    add("mattress-protector", "Quilted mattress protector", "beige", (226, 214, 190), 140, 190, shelf, attributes={"mattress_depth": 25, "attachment": "elastic skirt", "waterproof": "yes"})
    add("tablecloth", "White dining tablecloth", "white", (252, 252, 250), 140, 210, sideboard, material="linen", attributes={"shape": "rectangular"})
    add("curtain", "Sage living-room curtains", "sage", (150, 166, 142), 200, 250, None, material="linen", attributes={"panel_width": 200, "panel_count": 2, "attachment": "eyelets", "transparency": "opaque", "lining": "unlined"})
    add("curtain", "Short red curtain", "red", (176, 64, 54), 80, 100, box, attributes={"panel_width": 80, "panel_count": 1, "attachment": "loops", "transparency": "opaque"})
    add(
        "bath-towel",
        "White bath towel",
        "white",
        (245, 245, 245),
        70,
        140,
        cabinet,
        units=[
            (cabinet, "available"),
            (cabinet, "available"),
            (drawer, "in_laundry"),
            (None, "in_use"),
            (box, "available"),
            (box, "available"),
        ],
    )

    db.add(
        HouseholdObject(
            family_id=family.id,
            kind="bed",
            name="Main bed",
            home_id=home.id,
            room_id=bedroom.id,
            width=140,
            length=190,
            depth=20,
            attributes={"bed_type": "double"},
            notes="Mattress 140 × 190 cm, 20 cm deep.",
        )
    )
    db.add(
        HouseholdObject(
            family_id=family.id,
            kind="table",
            name="Dining table",
            home_id=home.id,
            room_id=dining.id,
            shape="rectangular",
            width=90,
            length=160,
            height=75,
            attributes={"table_type": "dining table"},
        )
    )
    db.add(
        HouseholdObject(
            family_id=family.id,
            kind="window",
            name="Living-room window",
            home_id=home.id,
            room_id=living.id,
            width=160,
            height=140,
            attributes={
                "window_type": "double",
                "rail_width": 200,
                "rail_to_floor": 250,
                "desired_length": 250,
                "fullness": 2,
                "panel_count": 2,
                "attachment": "eyelets",
            },
        )
    )
    db.commit()


def _location(db, family_id, room_id, parent_id, name, location_type):
    row = StorageLocation(
        family_id=family_id,
        room_id=room_id,
        parent_id=parent_id,
        name=name,
        location_type=location_type,
        qr_token=secrets.token_urlsafe(10),
    )
    db.add(row)
    db.flush()
    return row


def _swatch(family_id: int, rgb: tuple[int, int, int], label: str) -> tuple[str, str]:
    image = Image.new("RGB", (960, 640), rgb)
    draw = ImageDraw.Draw(image)
    ink = (250, 247, 240) if sum(rgb) < 420 else (48, 38, 30)
    draw.text((48, 300), label, fill=ink)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return save_photo(buffer.getvalue(), family_id)
