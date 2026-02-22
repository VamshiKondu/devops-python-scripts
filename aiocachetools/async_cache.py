"""Asynchronous cache decorators for coroutine functions and methods."""

import asyncio
from asyncio import Future, Task, shield
from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import AbstractContextManager
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import (
    Any,
    Protocol,
    TypeVar,
)

from cachetools.keys import hashkey
from loguru import logger

# Setup Loguru for library use
logger.disable(f"{__name__}")

_KT = TypeVar("_KT")
_T = TypeVar("_T")


class IdentityFunction(Protocol):
    """A callable that returns its first argument unchanged."""

    def __call__(self, x: _T, /) -> _T:
        """Return x unchanged."""
        ...


def apply_task_result_to_future(task: Task, future: Future) -> None:
    """Transfer the result or exception from task to future."""
    if task.cancelled():
        future.cancel()
        return

    exception = task.exception()
    if exception is not None:
        future.set_exception(exception)
        return

    future.set_result(task.result())


def _make_hashable(value: object) -> object:
    """Return a hashable representation for value."""
    try:
        hash(value)
        return value
    except Exception:
        return ("__id__", id(value))


def _filtered_key(
    key_func: Callable[..., _KT],
    fn: Callable[..., Awaitable],
    args: tuple[Any, ...],
    kwargs: MutableMapping[str, Any],
    ignore: tuple[int | str, ...] | None,
) -> _KT:
    sig = signature(fn)
    bound = sig.bind_partial(*args, **kwargs)
    bound.apply_defaults()

    ignore_set = set(ignore) if ignore is not None else set()
    bound_names = list(bound.arguments.keys())
    numeric_ignores = {i for i in ignore_set if isinstance(i, int)}
    name_ignores = {i for i in ignore_set if isinstance(i, str)}

    for idx, name in enumerate(bound_names):
        if idx in numeric_ignores:
            name_ignores.add(name)

    values = []
    for name in sig.parameters:
        if name not in bound.arguments or name in name_ignores:
            continue
        values.append(_make_hashable(bound.arguments[name]))

    return key_func(*values)


def cached(
    cache: MutableMapping[_KT, Future] | None,
    key: Callable[..., _KT] = hashkey,
    lock: AbstractContextManager[Any] | None = None,
    info: bool = False,
    ignore: tuple[int | str, ...] | None = None,
) -> IdentityFunction:
    """Wrap a coroutine function to save results in a cache.
    `ignore` can contain parameter names or 0-based positional indices
    to exclude from the cache key.

    Args:
        cache: A mutable mapping to use as the cache.
        key: A callable to generate cache keys.
        lock: Not supported, raises NotImplementedError.
        info: Not supported, raises NotImplementedError.
        ignore: A tuple of parameter names or indices to ignore in the cache key.

    Returns:
        A decorator that can be applied to coroutine functions.

    Raises:
        NotImplementedError: If `info` or `lock` is provided.
        TypeError: If the decorated function is not a coroutine function.
        ValueError: If the cache value is too large.

    Example:
    -------
    ```python

    ##Example of using `cached` with a TLRUCache and ignoring a parameter in the cache key.
    from cachetools import TLRUCache
    from async_cache import cached
    def ttu(key, value, time) -> float:
        return time + 10.0  # 10 seconds time-to-use
    @cached(cache=TLRUCache(maxsize=100, ttu=ttu), ignore=("param_to_ignore",))
    async def my_function(param1: int, param_to_ignore: str) -> int:
        # Simulate a slow operation
        await asyncio.sleep(1)
        return param1 * 2

    ##
    from cachetools import TLRUCache
    from async_cache import cached

    def ttu(key, value, time) -> float:
        return time + 10.0  # 10 seconds time-to-use

    class StaticMethod:
        call_count = 0
        # Use a single underscore to avoid complex name mangling in decorators
        _cache = TLRUCache(maxsize=10, ttu=lambda k, v, t: t + 10)

        @staticmethod
        @cached(cache=_cache, ignore=("b",))  # Use @cached and pass the cache directly
        async def static_add(a: int, b: int) -> int:
            StaticMethod.call_count += 1
            await asyncio.sleep(0.1)
            return a + b
    ```

    """
    if info or lock is not None:
        raise NotImplementedError("aiocachetools does not support `info` or `lock`")

    def decorator(fn: Callable[..., Awaitable]) -> Awaitable:
        if not iscoroutinefunction(fn):
            raise TypeError(f"Expected coroutine function, got {fn}")

        @wraps(fn)
        async def wrapper(*args: tuple[Any, ...], **kwargs: dict[str, Any]) -> _T:
            if cache is None:
                return await fn(*args, **kwargs)

            k = _filtered_key(key, fn, args, kwargs, ignore)
            future = cache.get(k)

            if future is not None:
                if future.done() and future.exception() is None:
                    logger.debug(f"Cache hit for {fn.__name__}")
                    return future.result()
                if not future.done():
                    return await shield(future)

            logger.debug(f"Cache miss for {fn.__name__}")
            f = asyncio.get_running_loop().create_future()
            task = asyncio.create_task(fn(*args, **kwargs))
            task.add_done_callback(lambda t: apply_task_result_to_future(t, f))

            try:
                cache[k] = f
            except ValueError:
                pass

            return await shield(f)

        wrapper.cache_clear = lambda: cache.clear() if cache is not None else None
        return wrapper

    return decorator


def cachedmethod(
    cache: Callable[[Any], MutableMapping[_KT, Future] | None],
    key: Callable[..., _KT] = hashkey,  # Fix: Use hashkey to avoid redundant ignoring
    ignore: tuple[int | str, ...] | None = None,
) -> IdentityFunction:
    """Wrap a coroutine method to save results in a cache.
    `ignore` can contain parameter names or 0-based positional indices
    to exclude from the cache key.

    Args:
     cache: A callable that takes the instance (self or cls) and returns a cache mapping.
     key: A callable to generate cache keys.
     lock: Not supported, raises NotImplementedError.
     ignore: A tuple of parameter names or indices to ignore in the cache key.

    Returns:
     A decorator that can be applied to coroutine methods.

    Raises:
     NotImplementedError: If `lock` is provided.
     TypeError: If the decorated method is not a coroutine function.
     ValueError: If the cache value is too large.

    Example:
    -------
    ```python
    from cachetools import TLRUCache
    from async_cache import cachedmethod
    def ttu(key, value, time) -> float:
        return time + 10.0  # 10 seconds time-to-use
    class MyClass:
        def __init__(self):
            self.cache = TLRUCache(maxsize=100, ttu=ttu)

        @cachedmethod(cache=lambda self: self.cache, ignore=("param_to_ignore",))
        async def my_method(self, param1: int, param_to_ignore: str) -> int:
            # Simulate a slow operation
            await asyncio.sleep(1)
            return param1 * 2
    ```

    """

    def decorator(actual_fn: Callable[..., Awaitable]) -> Awaitable:
        # Descriptor Unwrapping
        is_cls = isinstance(actual_fn, classmethod)
        is_static = isinstance(actual_fn, staticmethod)
        if is_cls or is_static:
            actual_fn = actual_fn.__func__

        if not iscoroutinefunction(actual_fn):
            raise TypeError(f"Expected coroutine function, got {actual_fn}")

        @wraps(actual_fn)
        async def wrapper(
            self_or_cls: object, *args: tuple[Any, ...], **kwargs: dict[str, Any]
        ) -> _T:
            c = cache(self_or_cls) if callable(cache) else cache
            if c is None:
                return await actual_fn(self_or_cls, *args, **kwargs)

            all_args = (self_or_cls,) + args
            k = _filtered_key(key, actual_fn, all_args, kwargs, ignore)
            future = c.get(k)

            if future is not None:
                if future.done() and future.exception() is None:
                    logger.debug(f"Cache hit for {actual_fn.__name__}")
                    return future.result()
                if not future.done():
                    return await shield(future)

            logger.debug(f"Cache miss for {actual_fn.__name__}")
            f = asyncio.get_running_loop().create_future()
            task = asyncio.create_task(actual_fn(self_or_cls, *args, **kwargs))
            task.add_done_callback(lambda t: apply_task_result_to_future(t, f))

            try:
                c[k] = f
            except ValueError:
                pass

            return await shield(f)

        # Re-wrap if necessary
        if is_cls:
            return classmethod(wrapper)
        if is_static:
            return staticmethod(wrapper)
        return wrapper

    return decorator
