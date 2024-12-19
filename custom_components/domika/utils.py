"""Domika homeassistant framework commonly used functions."""

from collections.abc import Generator, Iterable, Iterator, Mapping
import datetime
import enum
import itertools
from pathlib import Path
from typing import TypeVar
import threading

T = TypeVar("T")


def _json_encoder(obj: object) -> object:  # noqa: PLR0911
    """Convert objects to a form suitable for flattening."""
    if isinstance(obj, (set, tuple)):
        return list(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if hasattr(obj, "as_compressed_state"):
        return obj.as_compressed_state  # type: ignore[reportAttributeAccessIssue]
    if hasattr(obj, "as_dict"):
        return obj.as_dict()  # type: ignore[reportAttributeAccessIssue]
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    return obj


def _flatten(x: object, name: str, flattened_json: dict, exclude: set[str] | None):
    if exclude and name in exclude:
        return

    x = _json_encoder(x)

    if isinstance(x, dict):
        for a in x:
            _flatten(x[a], f"{name}.{a}" if name else a, flattened_json, exclude)
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

    Flatten json to the linear structure, excluding unwanted attributes including their
    children.

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
                'blip': 'blip',
            },
            exclude={'a.unwanted'},
        )
        returns
        {
            'a.b.c': 'test',
            'a.arr': '[1, 2, 3]',
            'blip': 'blip'
        }
    """
    flattened_json = {}
    _flatten(json, "", flattened_json, exclude)
    return flattened_json


def chunks(iterable: Iterable[T], size: int) -> Generator[Iterator[T], None, None]:
    """
    Iterate over iterable in chunks.

    Args:
        iterable: an iterable to iterate over.
        size: single chunk size.

    Yields:
        Iterator to a new chunk.
    """
    iterator = iter(iterable)
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, size - 1))


class ReadWriteLock:
    def __init__(self):
        self._readers = 0
        self._lock = threading.Lock()  # For synchronizing readers and writers
        self._write_lock = threading.Lock()  # Ensures only one writer

    def acquire_read(self):
        """Acquire the lock for reading."""
        with self._lock:
            self._readers += 1
            if self._readers == 1:  # First reader blocks writers
                self._write_lock.acquire()

    def release_read(self):
        """Release the lock for reading."""
        with self._lock:
            self._readers -= 1
            if self._readers == 0:  # Last reader releases writer lock
                self._write_lock.release()

    def acquire_write(self):
        """Acquire the lock for writing."""
        self._write_lock.acquire()

    def release_write(self):
        """Release the lock for writing."""
        self._write_lock.release()
