"""A tiny model layer that works with or without pydantic.

The game uses only a small slice of pydantic: ``BaseModel`` with typed fields and
``Field(default_factory=...)`` defaults, plus ``model_dump()`` / ``model_validate()``
for JSON round-tripping of nested models and enums.

When pydantic is installed we use it directly (fast, battle-tested). When it is
*not* - on iOS Python apps like a-Shell, or in a browser via Pyodide, where
pydantic's compiled Rust core will not install - we fall back to a pure
standard-library implementation of that same slice. This keeps the game
dependency-free everywhere while preserving exact save-file compatibility.

Set ``IRON_AND_ASH_NO_PYDANTIC=1`` to force the fallback (used by the test suite
to exercise it even where pydantic is available).
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, Union, get_args, get_origin, get_type_hints

_USE_PYDANTIC = False
if not os.environ.get("IRON_AND_ASH_NO_PYDANTIC"):
    try:  # pragma: no cover - depends on environment
        from pydantic import BaseModel, Field  # noqa: F401
        _USE_PYDANTIC = True
    except Exception:  # pragma: no cover
        _USE_PYDANTIC = False


if not _USE_PYDANTIC:
    _MISSING = object()

    class _FieldInfo:
        __slots__ = ("default", "default_factory")

        def __init__(self, default=_MISSING, default_factory=None):
            self.default = default
            self.default_factory = default_factory

    def Field(default=_MISSING, *, default_factory=None):  # noqa: N802 - mirror pydantic
        """Subset of ``pydantic.Field``: supports ``default`` and ``default_factory``."""
        return _FieldInfo(default, default_factory)

    def _coerce(typ, value):
        """Rebuild nested models / enums from plain JSON data on load."""
        if value is None:
            return None
        origin = get_origin(typ)
        if origin is Union:  # Optional[X] / Union[X, None]
            args = [a for a in get_args(typ) if a is not type(None)]  # noqa: E721
            return _coerce(args[0], value) if len(args) == 1 else value
        if origin in (list, tuple):
            args = get_args(typ)
            inner = args[0] if args else Any
            return [_coerce(inner, v) for v in value]
        if origin is dict:
            args = get_args(typ)
            vtyp = args[1] if len(args) == 2 else Any
            return {k: _coerce(vtyp, v) for k, v in value.items()}
        if isinstance(typ, type) and issubclass(typ, BaseModel):
            return typ.model_validate(value) if isinstance(value, dict) else value
        if isinstance(typ, type) and issubclass(typ, Enum):
            return value if isinstance(value, typ) else typ(value)
        return value

    def _dump(value):
        if isinstance(value, BaseModel):
            return value.model_dump()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {k: _dump(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_dump(v) for v in value]
        return value

    class BaseModel:
        """A minimal, mutable, JSON-round-trippable model base."""

        def __init__(self, **data):
            for name, spec in type(self)._model_fields().items():
                typ, has_default, default_factory, default_value = spec
                if name in data:
                    setattr(self, name, _coerce(typ, data[name]))
                elif default_factory is not None:
                    setattr(self, name, default_factory())
                elif has_default:
                    setattr(self, name, default_value)
                else:
                    raise TypeError(
                        f"{type(self).__name__} missing required field '{name}'")

        @classmethod
        def _model_fields(cls) -> Dict[str, tuple]:
            cached = cls.__dict__.get("__model_fields__")
            if cached is not None:
                return cached
            hints = get_type_hints(cls)
            fields: Dict[str, tuple] = {}
            for name, typ in hints.items():
                if name.startswith("_"):
                    continue
                raw = cls.__dict__.get(name, _MISSING)
                if isinstance(raw, _FieldInfo):
                    fields[name] = (typ, raw.default is not _MISSING,
                                    raw.default_factory,
                                    None if raw.default is _MISSING else raw.default)
                elif raw is _MISSING:
                    fields[name] = (typ, False, None, None)   # required
                else:
                    fields[name] = (typ, True, None, raw)     # plain default value
            cls.__model_fields__ = fields
            return fields

        @classmethod
        def model_validate(cls, data):
            if isinstance(data, cls):
                return data
            return cls(**data)

        def model_dump(self) -> dict:
            return {name: _dump(getattr(self, name))
                    for name in type(self)._model_fields()}

        def __repr__(self) -> str:
            inner = ", ".join(f"{k}={getattr(self, k)!r}"
                              for k in type(self)._model_fields())
            return f"{type(self).__name__}({inner})"


__all__ = ["BaseModel", "Field"]
