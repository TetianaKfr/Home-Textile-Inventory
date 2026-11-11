"""Reference data from the Home Textile Inventory SRS."""

COLORS = [
    "white", "ivory", "cream", "beige", "sand", "grey", "black", "navy", "blue",
    "light blue", "green", "sage", "pink", "red", "burgundy", "yellow", "gold",
    "orange", "brown", "purple", "multicolor",
]

PATTERNS = [
    "plain", "striped", "checked", "floral", "geometric", "abstract", "printed",
    "embroidered", "textured", "other",
]

MATERIALS = [
    "cotton", "linen", "polyester", "satin", "silk", "wool", "microfiber",
    "bamboo", "mixed", "unknown",
]

SEASONS = ["summer", "winter", "spring/autumn", "all-season"]

STATUSES = [
    "available", "in_use", "in_laundry", "temporarily_unavailable", "damaged", "archived",
]

FILLINGS = ["down", "feather", "wool", "cotton", "synthetic", "microfiber", "other", "unknown"]

CLOSURES = ["buttons", "zipper", "ties", "envelope", "other"]

ATTACHMENTS_CURTAIN = ["eyelets", "loops", "curtain tape", "hooks", "rings", "other"]

SHAPES = ["rectangular", "square", "round", "oval", "custom"]

ROLES = ["admin", "editor", "viewer"]

ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3}


def _num(key: str, label: str) -> dict:
    return {"key": key, "label": label, "type": "number", "unit": "cm"}


def _sel(key: str, label: str, options: list[str]) -> dict:
    return {"key": key, "label": label, "type": "select", "options": options}


def _text(key: str, label: str) -> dict:
    return {"key": key, "label": label, "type": "text"}


def category(
    slug: str,
    name: str,
    group: str,
    kind: str,
    dimensions: list[str],
    fields: list[dict] | None = None,
) -> dict:
    return {
        "slug": slug,
        "name": name,
        "group_name": group,
        "kind": kind,
        "attribute_schema": {"dimensions": dimensions, "fields": fields or []},
    }


def system_categories() -> list[dict]:
    bedding = "Bedding and bedroom textiles"
    bath = "Bathroom textiles"
    window = "Window and interior textiles"
    dining = "Dining textiles"
    other = "Other household textiles"
    return [
        category("bed-sheet", "Bed sheets", bedding, "textile", ["width", "length"], [
            _sel("sheet_type", "Sheet type", ["flat"]),
        ]),
        category("fitted-sheet", "Fitted sheets", bedding, "textile", ["width", "length"], [
            _sel("sheet_type", "Sheet type", ["fitted"]),
            _text("elastic", "Fitted sheet elastic configuration"),
            _num("mattress_depth", "Mattress depth compatibility"),
        ]),
        category("duvet-cover", "Duvet covers", bedding, "textile", ["width", "length"], [
            _sel("closure", "Closure type", CLOSURES),
            _sel("seasonality_hint", "Seasonality", SEASONS),
        ]),
        category("pillowcase", "Pillowcases", bedding, "textile", ["width", "length"], [
            _sel("closure", "Closure type", CLOSURES),
        ]),
        category("pillow-protector", "Pillow protectors", bedding, "textile", ["width", "length", "height"], [
            _sel("closure", "Closure type", CLOSURES),
        ]),
        category("mattress-protector", "Mattress protectors", bedding, "textile", ["width", "length"], [
            _num("mattress_depth", "Mattress depth"),
            _sel("attachment", "Attachment type", ["elastic skirt", "straps", "flat", "other"]),
            _sel("waterproof", "Waterproof", ["yes", "no", "unknown"]),
        ]),
        category("blanket", "Blankets", bedding, "textile", ["width", "length"], [
            _num("thickness", "Thickness"),
            _text("filling", "Filling, if applicable"),
        ]),
        category("duvet", "Duvets", bedding, "textile", ["width", "length"], [
            _num("thickness", "Thickness or loft"),
            _sel("season", "Season", SEASONS),
            _sel("filling", "Filling type", FILLINGS),
            _sel("warmth", "Warmth level", ["light", "medium", "warm", "unknown"]),
            _num("weight", "Weight (g)"),
        ]),
        category("pillow", "Pillows", bedding, "textile", ["width", "length", "height"], [
            _sel("filling", "Filling type", FILLINGS),
            _sel("firmness", "Firmness", ["soft", "medium", "firm", "unknown"]),
            _sel("shape", "Shape", ["rectangular", "square", "other"]),
            _num("weight", "Weight (g)"),
        ]),
        category("bedspread", "Bedspreads", bedding, "textile", ["width", "length"], [
            _num("thickness", "Thickness"),
            _text("filling", "Filling, if applicable"),
        ]),
        category("other-bedding", "Other bedding accessories", bedding, "textile", ["width", "length", "height"], []),
        category("bath-towel", "Bath towels", bath, "textile", ["width", "length"], []),
        category("hand-towel", "Hand towels", bath, "textile", ["width", "length"], []),
        category("face-towel", "Face towels", bath, "textile", ["width", "length"], []),
        category("bath-mat", "Bath mats", bath, "textile", ["width", "length"], []),
        category("other-bathroom", "Other bathroom textiles", bath, "textile", ["width", "length"], []),
        category("curtain", "Curtains", window, "textile", ["width", "length"], [
            _num("panel_width", "Panel width"),
            _num("panel_count", "Number of panels"),
            _sel("attachment", "Heading or attachment type", ATTACHMENTS_CURTAIN),
            _text("fabric_type", "Fabric type"),
            _sel("transparency", "Transparency", ["opaque", "semi-sheer", "sheer", "unknown"]),
            _sel("lining", "Lining", ["lined", "unlined", "blackout", "unknown"]),
            _num("fullness", "Recommended fullness ratio"),
        ]),
        category("drape", "Drapes", window, "textile", ["width", "length"], [
            _num("panel_width", "Panel width"),
            _num("panel_count", "Number of panels"),
            _sel("attachment", "Heading or attachment type", ATTACHMENTS_CURTAIN),
            _sel("lining", "Lining", ["lined", "unlined", "blackout", "unknown"]),
        ]),
        category("sheer-curtain", "Sheer curtains", window, "textile", ["width", "length"], [
            _num("panel_width", "Panel width"),
            _num("panel_count", "Number of panels"),
            _sel("attachment", "Heading or attachment type", ATTACHMENTS_CURTAIN),
        ]),
        category("other-window", "Other window textiles", window, "textile", ["width", "length"], []),
        category("tablecloth", "Tablecloths", dining, "textile", ["width", "length", "diameter"], [
            _sel("shape", "Shape", SHAPES),
            _num("overhang", "Desired overhang"),
        ]),
        category("table-runner", "Table runners", dining, "textile", ["width", "length"], []),
        category("placemat", "Placemats", dining, "textile", ["width", "length"], [
            _sel("shape", "Shape", SHAPES),
        ]),
        category("other-dining", "Other dining textiles", dining, "textile", ["width", "length"], []),
        category("other-textile", "Other textile items", other, "textile", ["width", "length", "height", "diameter"], []),
    ]


DEFAULT_PREFERENCES = {
    "table_overhang_cm": 25,
    "sheet_side_overhang_cm": 25,
    "sheet_head_overhang_cm": 30,
    "sheet_foot_overhang_cm": 20,
    "size_tolerance_cm": 3,
    "duvet_tolerance_cm": 3,
    "pillow_allowance_cm": 8,
    "curtain_fullness": 2.0,
}


OBJECT_KINDS = ["bed", "mattress", "table", "window"]
