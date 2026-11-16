from types import SimpleNamespace

from app.services.matching import _assign_bed_pillows, _bed_pillow_sizes, _home_scope, _scope_to_home, _usable_units


class _Unit:
    def __init__(self, status="available", archived=False):
        self.status = status
        self.archived = archived
        self.location_id = None


class _Category:
    name = "Pillowcases"
    slug = "pillowcase"


def _case(item_id, width, length, quantity=1, damaged=0):
    units = [_Unit() for _ in range(quantity)]
    units.extend(_Unit(status="damaged") for _ in range(damaged))
    return SimpleNamespace(
        id=item_id,
        name=f"Case {item_id}",
        width=width,
        length=length,
        height=None,
        diameter=None,
        attributes={},
        primary_color="white",
        material="cotton",
        pattern="plain",
        photos=[],
        category=_Category(),
        units=units,
    )


def _assign(sizes, cases):
    rejected = []
    plan = _assign_bed_pillows(sizes, cases, lambda _location: "", {}, rejected)
    return plan, rejected


def test_home_search_drops_textiles_stored_in_another_home():
    at_home = SimpleNamespace(archived=False, status="available", location_id=10)
    elsewhere = SimpleNamespace(archived=False, status="available", location_id=20)
    case = SimpleNamespace(id=1, category=SimpleNamespace(slug="pillowcase"), units=[at_home, elsewhere])
    duvet = SimpleNamespace(id=2, category=SimpleNamespace(slug="duvet"), units=[elsewhere])
    scoped = _scope_to_home([case, duvet], {10})
    assert [item.id for item in scoped] == [1]
    assert _usable_units(scoped[0]) == [at_home]
    assert _scope_to_home([case], set()) == []
    assert _scope_to_home([case], None) == [case]


def test_home_scope_names_all_homes_or_the_chosen_home():
    homes = [SimpleNamespace(id=4, name="Michel, Saint-Malo")]
    rooms = [SimpleNamespace(id=8, home_id=4)]
    locations = [SimpleNamespace(id=15, room_id=8), SimpleNamespace(id=16, room_id=9)]
    assert _home_scope(homes, rooms, locations, None) == (None, "all homes")
    location_ids, label = _home_scope(homes, rooms, locations, 4)
    assert location_ids == {15}
    assert label == "Michel, Saint-Malo"


def test_bed_pillow_sizes_come_from_the_bed_only():
    bed = SimpleNamespace(
        kind="bed",
        attributes={
            "pillows": [
                {"width": 60, "length": 60},
                {"width": 60, "length": 60},
                {"width": "", "length": 40},
                {"width": 60, "length": 40},
            ]
        },
    )
    assert _bed_pillow_sizes(bed) == [
        {"width": 60, "length": 60},
        {"width": 60, "length": 60},
        {"width": 60, "length": 40},
    ]
    mattress = SimpleNamespace(kind="mattress", attributes={"pillows": [{"width": 60, "length": 60}]})
    assert _bed_pillow_sizes(mattress) == []


def test_pillowcase_quantity_covers_one_pillow_per_unit():
    sizes = [
        {"width": 60, "length": 60},
        {"width": 60, "length": 60},
        {"width": 60, "length": 60},
        {"width": 60, "length": 40},
    ]
    first = _case(1, 60, 60, quantity=2)
    second = _case(2, 60, 60, quantity=1)
    close_but_not_exact = _case(4, 65, 65, quantity=1)
    too_small = _case(3, 40, 40, quantity=1)
    plan, rejected = _assign(sizes, [first, second, close_but_not_exact, too_small])

    assert [row["item_id"] for row in plan["rows"]] == [1, 1, 2]
    assert "Bed pillow 1: 60 × 60 cm." in plan["rows"][0]["technical"]["explanation"]
    assert "Bed pillow 3: 60 × 60 cm." in plan["rows"][2]["technical"]["explanation"]
    assert plan["missing"] == [
        {
            "category": "Pillowcase",
            "reason": "1 suitable pillowcase is still missing.",
            "required": "60 × 40 cm",
        }
    ]
    assert [row["item_id"] for row in rejected] == [3]
    assert rejected[0]["technical"]["explanation"] == "The pillowcase does not fit any pillow size on this bed."


def test_three_pillows_and_two_units_report_one_missing():
    sizes = [
        {"width": 60, "length": 60},
        {"width": 60, "length": 60},
        {"width": 60, "length": 60},
    ]
    plan, _rejected = _assign(sizes, [_case(1, 60, 60, quantity=1), _case(2, 60, 60, quantity=1)])
    assert [row["item_id"] for row in plan["rows"]] == [1, 2]
    assert plan["missing"] == [
        {
            "category": "Pillowcase",
            "reason": "1 suitable pillowcase is still missing.",
            "required": "60 × 60 cm",
        }
    ]


def test_same_missing_size_is_counted_together():
    sizes = [{"width": 60, "length": 60}, {"width": 60, "length": 60}]
    plan, rejected = _assign(sizes, [_case(1, 50, 50)])
    assert plan["rows"] == []
    assert plan["missing"] == [
        {
            "category": "Pillowcase",
            "reason": "2 suitable pillowcases are still missing.",
            "required": "60 × 60 cm",
        }
    ]
    assert [row["item_id"] for row in rejected] == [1]


def test_damaged_pillowcase_units_are_not_used():
    plan, _rejected = _assign([{"width": 60, "length": 60}], [_case(1, 60, 60, quantity=0, damaged=2)])
    assert plan["rows"] == []
    assert plan["missing"][0]["required"] == "60 × 60 cm"
