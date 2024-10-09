# vim: set fileencoding=utf-8
"""
Cache functions.

(c) DevPocket, 2024


Author(s): Artem Bezborodko
"""

import asyncio
import functools
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    ParamSpec,
    TypeVar,
    final,
    overload,
)

T = TypeVar("T")
Param = ParamSpec("Param")


@final
class _CacheWrapper(Generic[Param, T]):
    __wrapped__: Callable[Param, Awaitable[T]]

    without_cache: Callable[Param, Awaitable[T]]

    async def __call__(self, *args: Param.args, **kwargs: Param.kwargs) -> T: ...  # pylint: disable=no-member
    def cache_clear(self) -> None:
        """Clear cache."""

    def cache_size(self) -> int:  # type: ignore
        """
        Get cache size.

        Returns:
            current cache size.
        """


class CacheKey:
    """
    Cache key representation.

    Need for better typing.
    """

    def __init__(self, h: int) -> None:
        self.hash = h

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, CacheKey):
            return self.hash == other.hash
        return NotImplemented

    def __hash__(self) -> int:
        return self.hash


def cache_key(*args, **kwargs) -> CacheKey:
    """
    Default cache key generation function.

    Uses args and kwargs as input value for the hash function.
    kwargs preserve the order input by the user, it means that f(x=1, y=2) will be treated as a
    distinct call from f(y=2, x=1) which will be cached separately.

    Returns:
        generated cache key.
    """
    key = args
    if kwargs:
        key += (object(),)  # kwargs separator
        for item in kwargs.items():
            key += item

    h = hash(args)

    return CacheKey(h)


def _cache_wrapper(
    user_function: Callable[..., Awaitable[T]],
    cache_key_: Callable[..., CacheKey],
) -> Callable[..., Awaitable[T]]:
    cache = {}

    def _clear() -> None:
        cache.clear()

    def _size() -> int:
        return len(cache)

    async def _inner(*args, **kwargs) -> Any:
        key = cache_key_(*args, **kwargs)
        if key not in cache:
            cache[key] = await user_function(*args, **kwargs)
        return cache[key]

    _inner.without_cache = user_function  # type: ignore
    _inner.cache_clear = _clear  # type: ignore
    _inner.cache_size = _size  # type: ignore

    return _inner  # type: ignore


@overload
def cached(
    cache_key_fn: Callable[Param, Awaitable[T]],
) -> _CacheWrapper[Param, T]: ...


@overload
def cached(
    cache_key_fn: Callable[..., CacheKey] = cache_key,
) -> Callable[[Callable[Param, Awaitable[T]]], _CacheWrapper[Param, T]]: ...


def cached(
    cache_key_fn=cache_key,
) -> _CacheWrapper[Param, T] | Callable[[Callable[Param, Awaitable[T]]], _CacheWrapper[Param, T]]:
    """
    Decorator that caches returned value.

    Arguments to the cached function must be hashable.
    kwargs preserve the order input by the user, it means that f(x=1, y=2) will be treated as a
    distinct call from f(y=2, x=1) which will be cached separately.

    Warning! This decorator will never clear cached values automatically. You should manually call
    cache_clear, when it is needed.

    Args:
        cache_key_fn: user defined cache key generation function in case when decorator used with
        parameters, or wrapped function itself. Defaults to cache_key.

    Returns:
        _CacheWrapper object, or function that return _CacheWrapper in case when decorator used with
        parameters.
    """
    if asyncio.iscoroutinefunction(cache_key_fn):
        # If cache_key_fn is a coroutine - that means that the decorator called without any
        # parameters. So cache_key_fn is a wrapped user function.
        wrapped = cache_key_fn
        wrapper = _cache_wrapper(wrapped, cache_key)
        return functools.update_wrapper(wrapper, wrapped)  # type: ignore

    def decorating_function(
        wrapped: Callable[Param, Awaitable[T]],
    ) -> Callable[[Callable[Param, Awaitable[T]]], _CacheWrapper[Param, T]]:
        # wrapped - is a user function.
        wrapper = _cache_wrapper(wrapped, cache_key_fn)
        return functools.update_wrapper(wrapper, wrapped)  # type: ignore

    return decorating_function  # type: ignore
