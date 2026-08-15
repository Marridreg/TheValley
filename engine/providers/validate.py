"""A minimal JSON Schema validator for the subset schemas.py uses.

Only needed on the prompted-JSON fallback path, where a model may return
something structurally wrong. Hand-rolled rather than pulling in `jsonschema`
because the subset is small and closed — object/array/scalar, type unions,
enum, required, additionalProperties — and because the error messages here are
written to be fed straight back to a model as a repair instruction, which
generic validator output is bad at.

Not a general-purpose validator. It covers exactly what BRIEFING_SCHEMA can
express and treats anything else as valid rather than guessing.
"""

from __future__ import annotations

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(data, schema: dict, path: str = "$") -> list[str]:
    """Return a list of human-readable problems. Empty means valid."""
    errors: list[str] = []

    expected = schema.get("type")
    if expected is not None:
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(_TYPE_CHECKS.get(t, lambda _v: True)(data) for t in allowed):
            errors.append(
                f"{path}: expected {' or '.join(allowed)}, got "
                f"{_type_name(data)}"
            )
            # Type is wrong, so descending would only produce noise.
            return errors

    if "enum" in schema and data not in schema["enum"]:
        errors.append(
            f"{path}: must be one of {schema['enum']}, got {data!r}"
        )

    if isinstance(data, dict) and _permits(expected, "object"):
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}.{key}: missing required field")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in data:
                if key not in props:
                    errors.append(f"{path}.{key}: unexpected field, not in schema")
        for key, subschema in props.items():
            if key in data:
                errors.extend(validate(data[key], subschema, f"{path}.{key}"))

    if isinstance(data, list) and _permits(expected, "array"):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(data):
                errors.extend(validate(item, item_schema, f"{path}[{i}]"))

    return errors


def _permits(expected, kind: str) -> bool:
    if expected is None:
        return True
    allowed = expected if isinstance(expected, list) else [expected]
    return kind in allowed


def _type_name(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def describe_errors(errors: list[str], limit: int = 12) -> str:
    """Compact the error list into a repair instruction."""
    shown = errors[:limit]
    text = "\n".join(f"  - {e}" for e in shown)
    if len(errors) > limit:
        text += f"\n  - ... and {len(errors) - limit} more"
    return text
