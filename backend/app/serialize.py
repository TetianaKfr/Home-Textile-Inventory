from app.services.dimensions import size_label


def user_brief(user) -> dict:
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "notify_changes": user.notify_changes}


def category_dict(category) -> dict:
    return {
        "id": category.id,
        "slug": category.slug,
        "name": category.name,
        "group_name": category.group_name,
        "kind": category.kind,
        "attribute_schema": category.attribute_schema or {"dimensions": [], "fields": []},
        "custom": category.family_id is not None,
    }


def item_dict(item, path) -> dict:
    units = []
    for unit in item.units:
        if unit.archived:
            continue
        units.append(
            {
                "id": unit.id,
                "status": unit.status,
                "notes": unit.notes,
                "location_id": unit.location_id,
                "location_path": path(unit.location_id),
            }
        )
    photos = [
        {"id": photo.id, "is_main": photo.is_main, "created_at": photo.created_at.isoformat() if photo.created_at else None}
        for photo in sorted(item.photos, key=lambda photo: (not photo.is_main, photo.id))
    ]
    return {
        "id": item.id,
        "category": category_dict(item.category) if item.category else None,
        "name": item.name,
        "description": item.description,
        "brand": item.brand,
        "primary_color": item.primary_color,
        "secondary_colors": item.secondary_colors or [],
        "pattern": item.pattern,
        "texture": item.texture,
        "material": item.material,
        "seasonality": item.seasonality,
        "notes": item.notes,
        "width": item.width,
        "length": item.length,
        "height": item.height,
        "diameter": item.diameter,
        "dimensions_label": size_label(item.width, item.length, item.diameter),
        "attributes": item.attributes or {},
        "field_sources": item.field_sources or {},
        "version": item.version,
        "archived": item.archived,
        "quantity": len(units),
        "units": units,
        "photos": photos,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def object_dict(obj, home_name: str = "", room_name: str = "") -> dict:
    return {
        "id": obj.id,
        "kind": obj.kind,
        "name": obj.name,
        "home_id": obj.home_id,
        "room_id": obj.room_id,
        "home_name": home_name,
        "room_name": room_name,
        "shape": obj.shape,
        "width": obj.width,
        "length": obj.length,
        "height": obj.height,
        "diameter": obj.diameter,
        "depth": obj.depth,
        "attributes": obj.attributes or {},
        "notes": obj.notes,
        "dimensions_label": size_label(obj.width, obj.length, obj.diameter),
    }
