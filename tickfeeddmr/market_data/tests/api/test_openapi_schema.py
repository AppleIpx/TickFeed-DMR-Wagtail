from __future__ import annotations

import inspect
import typing
from decimal import Decimal

import msgspec
import openapi_spec_validator
import pytest

from config.api_router import schema
from tickfeeddmr.market_data.api.schemas import common, crypto, fiat, stock

_SCHEMA_MODULES = (common, crypto, fiat, stock)


def test_openapi_schema_builds_and_validates() -> None:
    spec = schema.convert()

    openapi_spec_validator.validate(spec)


def _mentions_decimal(annotation: object) -> bool:
    if annotation is Decimal:
        return True
    return any(_mentions_decimal(arg) for arg in typing.get_args(annotation))


def _iter_struct_classes() -> list[type[msgspec.Struct]]:
    classes = []
    for module in _SCHEMA_MODULES:
        for _, obj in inspect.getmembers(module):
            if (
                isinstance(obj, type)
                and issubclass(obj, msgspec.Struct)
                and obj.__module__ == module.__name__
            ):
                classes.append(obj)
    return classes


@pytest.mark.parametrize("struct_cls", _iter_struct_classes())
def test_schema_struct_has_no_decimal_fields(
    struct_cls: type[msgspec.Struct],
) -> None:
    for field in msgspec.structs.fields(struct_cls):
        assert not _mentions_decimal(field.type), (
            f"{struct_cls.__name__}.{field.name} использует Decimal напрямую "
            "в API-схеме — ценовые поля должны быть str (баг OpenAPI-схемы "
            "django-modern-rest с форматом 'decimal')"
        )
