from functools import cache
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, create_model

from nexus.nodes.spec import FieldKind, FieldSpec


class SecretRef(BaseModel):
    """Names an entry in the secrets service. Raw values cannot pass this type."""

    model_config = ConfigDict(extra="forbid")

    secret: str = Field(pattern=r"^[A-Za-z0-9_.\-]{1,120}$")


def _python_type(field: FieldSpec) -> Any:
    bounds = {
        key: value
        for key, value in (("ge", field.minimum), ("le", field.maximum))
        if value is not None
    }
    match field.kind:
        case FieldKind.TEXT | FieldKind.TEXTAREA | FieldKind.CODE:
            return str
        case FieldKind.NUMBER | FieldKind.SLIDER:
            return Annotated[float, Field(strict=True, **bounds)]
        case FieldKind.BOOLEAN:
            return bool
        case FieldKind.SELECT:
            return Literal[tuple(field.options)]
        case FieldKind.MULTI_SELECT:
            return list[Literal[tuple(field.options)]]
        case FieldKind.JSON:
            return JsonValue
        case FieldKind.SECRET:
            return SecretRef
        case FieldKind.ARRAY:
            return list[_python_type(field.item)]
        case FieldKind.OBJECT:
            return build_model(field.name, tuple(field.fields))


def build_model(name: str, fields: tuple[FieldSpec, ...]) -> type[BaseModel]:
    """Compiles field specs into a strict Pydantic model. Everything is optional here:
    requiredness depends on visibility, so `required_errors` decides it."""
    definitions = {field.name: (_python_type(field) | None, None) for field in fields}
    return create_model(f"{name}Config", __config__=ConfigDict(extra="forbid"), **definitions)


def _is_visible(field: FieldSpec, config: dict[str, Any]) -> bool:
    condition = field.visible_when
    return condition is None or config.get(condition.field) in condition.equals


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def required_errors(
    fields: list[FieldSpec], config: dict[str, Any], prefix: str = ""
) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    for field in fields:
        if not _is_visible(field, config):
            continue
        value = config.get(field.name)
        if field.required and _is_empty(value):
            errors.append((f"{prefix}{field.name}", f"{field.label} is required"))
        if field.kind is FieldKind.OBJECT and isinstance(value, dict):
            errors += required_errors(field.fields, value, f"{prefix}{field.name}.")
    return errors


@cache
def _cached_model(key: str, fields: tuple[str, ...]) -> type[BaseModel]:
    return build_model(key, tuple(FieldSpec.model_validate_json(f) for f in fields))


def validate_config(
    name: str, fields: list[FieldSpec], config: dict[str, Any]
) -> list[tuple[str, str]]:
    """Returns (field path, message) pairs; an empty list means the config is valid."""
    model = _cached_model(name, tuple(field.model_dump_json() for field in fields))
    try:
        model.model_validate(config)
    except ValidationError as error:
        return [
            (".".join(str(part) for part in item["loc"]), item["msg"]) for item in error.errors()
        ]
    return required_errors(fields, config)
