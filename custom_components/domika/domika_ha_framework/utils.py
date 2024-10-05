# vim: set fileencoding=utf-8
"""
Domika integration.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import datetime
import enum
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def _json_encoder(obj: Any) -> Any:  # noqa: PLR0911
    """Convert objects to a form suitable for flatterization."""
    if isinstance(obj, (set, tuple)):
        return list(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if hasattr(obj, 'as_compressed_state'):
        return obj.as_compressed_state
    if hasattr(obj, 'as_dict'):
        return obj.as_dict()
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    return obj


def _flatten(x: Any, name: str, flattened_json: dict, exclude: set[str] | None):
    if exclude and name in exclude:
        return

    x = _json_encoder(x)

    if isinstance(x, dict):
        for a in x:
            _flatten(x[a], f'{name}.{a}' if name else a, flattened_json, exclude)
    elif isinstance(x, Iterable):
        if not isinstance(x, (str, bytes, bytearray)):
            flattened_json[name] = str([_json_encoder(i) for i in x])
        else:
            flattened_json[name] = str(x)
    elif x is not None:
        flattened_json[name] = str(x)


def flatten_json(json: Mapping, exclude: set[str] | None = None) -> dict:
    """
    Generate flattened json dict.

    Flatten json to the linear structure, excluding unwanted attributes including their children.

    Args:
        json: original json dict.
        exclude: Set of excluded flattened names. Defaults to None.

    Returns:
        Flattened json dict.
        E.g:
        flatten_json(
            {
                'a': {
                    'b': {
                        'c': 'test',
                    },
                    'unwanted': {
                        'buggy stuff': 'DEAD_BEEF',
                        'nested': {
                            'ignored': 'too',
                        },
                    },
                    'arr': [1, 2, 3],
                },
                'blip': 'blop',
            },
            exclude={'a.unwanted'},
        )
        returns
        {
            'a.b.c': 'test',
            'a.arr': '[1, 2, 3]',
            'blip': 'blop'
        }
    """
    flattened_json = {}
    _flatten(json, '', flattened_json, exclude)
    return flattened_json
