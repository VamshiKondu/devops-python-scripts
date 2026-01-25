import asyncio
from collections.abc import Generator
from typing import Any

import pytest
from cachetools import TLRUCache
from loguru import logger

from async_cache import cached, cachedmethod


@pytest.fixture
def enabled_log() -> Generator[Any, Any, Any]:
    """Fixture to enable loguru logging for async_cache during tests."""
    # Enable before the test starts
    logger.enable("async_cache")
    yield
    # Disable again after the test finished to keep other tests clean
    logger.disable("async_cache")


@pytest.mark.asyncio
async def test_cached_ignore_param_name() -> None:
    """Test that the `ignore` parameter in the `cached` decorator works correctly."""
    call_count = 0

    def ttu(key, value, time) -> float:
        return time + 2.0  # 2 seconds time-to-use

    @cached(cache=TLRUCache(maxsize=10, ttu=ttu), ignore=("a",))
    async def add(a: int, b: int) -> int:
        nonlocal call_count
        call_count += 1
        return a + b

    result1 = await add(1, 2)
    result2 = await add(1, 2)  # b is ignored in cache key

    assert result1 == 3
    assert result2 == 3
    assert call_count == 1  # Function called only once


@pytest.mark.asyncio
async def test_cache_expiry() -> None:
    """Test that cached values expire correctly based on TLRUCache settings."""
    call_count = 0

    def ttu(key, value, time) -> float:
        return time + 1.0  # 1 second time-to-use

    @cached(cache=TLRUCache(maxsize=10, ttu=ttu))
    async def multiply(a: int, b: int) -> int:
        nonlocal call_count
        call_count += 1
        return a * b

    result1 = await multiply(2, 3)
    result2 = await multiply(2, 3)  # Should hit cache

    assert result1 == 6
    assert result2 == 6
    assert call_count == 1  # Function called only once

    await asyncio.sleep(1.1)  # Wait for cache to expire

    result3 = await multiply(2, 3)  # Should recompute

    assert result3 == 6
    assert call_count == 2  # Function called again after expiry


@pytest.mark.asyncio
async def test_concurrent_calls() -> None:
    """Test that concurrent calls to a cached function work correctly."""
    call_count = 0

    def ttu(key, value, time) -> float:
        return time + 5.0  # 5 seconds time-to-use

    cache = TLRUCache(maxsize=10, ttu=ttu)

    @cached(cache=cache)
    async def slow_add(a: int, b: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.5)  # Simulate a slow operation
        return a + b

    results = await asyncio.gather(
        slow_add(1, 2),
        slow_add(1, 2),
        slow_add(1, 2),
    )

    assert results == [3, 3, 3]
    assert call_count == 1  # Function called only once despite concurrent calls
    result4 = await slow_add(1, 2)
    assert result4 == 3
    assert call_count == 1  # Still only one call due to caching


@pytest.mark.asyncio
async def test_cache_clear() -> None:
    """Test that the cache_clear method works correctly."""
    call_count = 0

    def ttu(key, value, time) -> float:
        return time + 5.0  # 5 seconds time-to-use

    @cached(cache=TLRUCache(maxsize=10, ttu=ttu))
    async def slow_add(a: int, b: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.5)  # Simulate a slow operation
        return a + b

    result1 = await slow_add(1, 2)
    assert result1 == 3
    assert call_count == 1

    result2 = await slow_add(1, 2)
    assert result2 == 3
    assert call_count == 1  # Cached result

    slow_add.cache_clear()  # Clear the cache

    result3 = await slow_add(1, 2)
    assert result3 == 3
    assert call_count == 2  # Function called again after cache clear


@pytest.mark.asyncio
async def test_size_limit() -> None:
    """Test that the cache respects the size limit."""

    def ttu(key, value, time) -> float:
        return time + 10.0  # 10 seconds time-to-use

    cache = TLRUCache(maxsize=2, ttu=ttu)

    @cached(cache=cache)
    async def add(a: int, b: int) -> int:
        return a + b

    await add(a=1, b=2)  # Cache: {(1,2)}
    await add(a=2, b=3)  # Cache: {(1,2), (2,3)}
    await add(a=3, b=4)  # Cache should evict (1,2); Cache: {(2,3), (3,4)}

    assert (1, 2) not in cache
    assert (2, 3) in cache
    assert (3, 4) in cache


################################cachemethod tests###############################


@pytest.mark.asyncio
async def test_cachemethod_staticmethod() -> None:
    """Test that the cached decorator works with static methods."""

    class MathOps:
        call_count = 0

        @staticmethod
        @cached(cache=TLRUCache(maxsize=10, ttu=lambda k, v, t: t + 10), ignore=("a",))
        async def static_multiply(a: int, b: int) -> int:
            MathOps.call_count += 1
            await asyncio.sleep(0.1)
            return a * b

    result1 = await MathOps.static_multiply(2, 3)
    result2 = await MathOps.static_multiply(2, 3)  # Should hit cache

    assert result1 == 6
    assert result2 == 6
    assert MathOps.call_count == 1  # Function called only once


@pytest.mark.asyncio
async def test_classmethod_cache(enabled_log) -> None:
    """Test that the cached decorator works with class methods."""

    class MathOps:
        call_count = 0
        __cache = TLRUCache(maxsize=10, ttu=lambda k, v, t: t + 10)

        @classmethod
        @cachedmethod(
            cache=lambda cls: cls._MathOps__cache,
            ignore=("a",),
        )
        async def class_add(cls, a: int, b: int) -> int:
            cls.call_count += 1
            await asyncio.sleep(0.1)
            return a + b

    result1 = await MathOps.class_add(a=4, b=5)
    result2 = await MathOps.class_add(a=4, b=5)  # Should hit
    result3 = await MathOps.class_add(0, b=4)  # Should hit
    assert result1 == 9
    assert result2 == 9
    assert result3 == 4
    assert MathOps.call_count == 2


@pytest.mark.asyncio
async def test_instance_method_cache() -> None:
    """Test that the cachedmethod decorator works with instance methods."""

    class Counter:
        def __init__(self) -> None:
            self.call_count = 0
            self._cache = TLRUCache(maxsize=10, ttu=lambda k, v, t: t + 10)

        @cachedmethod(cache=lambda self: self._cache)
        async def increment(self, value: int) -> int:
            self.call_count += 1
            await asyncio.sleep(0.1)
            return value + 1

    counter = Counter()
    result1 = await counter.increment(5)
    result2 = await counter.increment(5)  # Should hit cache
    result3 = await counter.increment(6)  # Should hit cache

    assert result1 == 6
    assert result2 == 6
    assert result3 == 7
    assert counter.call_count == 2  # Function called only twice
