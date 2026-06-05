from typing import Any


def handle_uppercase(config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    result = dict(inputs)
    for key, value in list(result.items()):
        if isinstance(value, str):
            result[key] = value.upper()
        elif isinstance(value, dict):
            result[key] = {k: v.upper() if isinstance(v, str) else v for k, v in value.items()}
    return result


def handle_concat(config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    separator = config.get("separator", "")
    fields = config.get("fields", [])
    if not isinstance(fields, list):
        raise ValueError("concat config.fields must be a list")

    def find_field(data: dict[str, Any], field: str) -> Any | None:
        if field in data:
            return data[field]
        for value in data.values():
            if isinstance(value, dict):
                found = find_field(value, field)
                if found is not None:
                    return found
        return None

    parts: list[str] = []
    for field in fields:
        value = find_field(inputs, field)
        if value is not None:
            parts.append(str(value))

    return {**inputs, "concatenated": separator.join(parts)}


def handle_constant(config: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    key = config.get("key", "value")
    value = config.get("value")
    return {**inputs, key: value}
