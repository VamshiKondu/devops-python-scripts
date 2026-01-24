import asyncio
import logging

import pytest
from cachetools import TLRUCache

from async_cache import cached

# Define the logger for your package
logger = logging.getLogger("aiocachetools")
# Add NullHandler so it stays silent by default
logger.addHandler(logging.NullHandler())


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
