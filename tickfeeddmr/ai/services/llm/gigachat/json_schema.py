from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

_KEPT_KEYS = ("type", "enum", "items")
_FORMAT_HINTS = {"date": "формат YYYY-MM-DD", "date-time": "формат ISO 8601"}


def _simplify_property(prop: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(prop)
    branches = merged.pop("anyOf", None)
    if branches:
        non_null = [b for b in branches if b.get("type") != "null"]
        if non_null:
            merged = {**non_null[0], **merged}

    enum = merged.get("enum")
    if enum is not None and "type" not in merged:
        all_ints = all(isinstance(v, int) and not isinstance(v, bool) for v in enum)
        merged["type"] = "integer" if all_ints else "string"

    result = {key: merged[key] for key in _KEPT_KEYS if key in merged}
    result.setdefault("type", "string")

    description = merged.get("description", "")
    hint = _FORMAT_HINTS.get(merged.get("format", ""))
    if hint:
        description = f"{description} ({hint})".strip()
    if description:
        result["description"] = description
    return result


def to_gigachat_parameters(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Упростить плоскую JSON Schema аргументов так, чтобы SDK её не искажал."""
    properties = {
        name: _simplify_property(prop)
        for name, prop in schema.get("properties", {}).items()
    }
    result: dict[str, Any] = {"type": "object", "properties": properties}
    if schema.get("required"):
        result["required"] = list(schema["required"])
    return result
