import asyncio

from cachetools import TLRUCache
from loguru import logger

from async_cache import cached, cachedmethod

logger.enable("async_cache")


class SelfMethod:
    def __init__(self) -> None:
        self.call_count = 0
        self._cache = TLRUCache(maxsize=1, ttu=lambda k, v, t: t + 10)

    @cachedmethod(cache=lambda self: self._cache, ignore=("b",))
    async def add(self, a: int, b: int) -> int:
        self.call_count += 1
        logger.debug(f"add called with values: {a}, {b}")
        await asyncio.sleep(0.1)
        return a + b


@cached(cache=TLRUCache(maxsize=1, ttu=lambda k, v, t: t + 10))
async def global_function(a: int, b: int) -> int:
    return a + b


class StaticMethod:
    call_count = 0
    # Use a single underscore to avoid complex name mangling in decorators
    _cache = TLRUCache(maxsize=1, ttu=lambda k, v, t: t + 10)

    @staticmethod
    @cached(cache=_cache, ignore=("b",))  # Use @cached and pass the cache directly
    async def static_add(a: int, b: int) -> int:
        StaticMethod.call_count += 1
        await asyncio.sleep(0.1)
        return a + b


class ClassMethod:
    call_count = 0
    _cache = TLRUCache(maxsize=1, ttu=lambda k, v, t: t + 10)

    @classmethod
    @cachedmethod(
        cache=lambda cls: cls._cache, ignore=("b",)
    )  # Use @cachedmethod and pass the cache via lambda
    async def class_add(cls, a: int, b: int) -> int:
        """Example of a class method using cachedmethod with a TLRUCache."""
        cls.call_count += 1
        await asyncio.sleep(0.1)
        return a + b


async def main() -> None:
    result = await global_function(2, 3)
    assert result == 5
    result = await global_function(2, 3)
    assert result == 5
    result = await global_function(2, 5)
    assert result == 7
    result = await global_function(2, 3)
    assert result == 5

    counter = SelfMethod()
    result1 = await counter.add(5, 1)
    result2 = await counter.add(5, 2)  # Should miss cache, since 'b' is ignored
    result3 = await counter.add(6, 1)  # Should hit cache
    result4 = await counter.add(5, 2)  # Should hit cache
    assert result1 == 6
    assert result2 == 6
    assert result3 == 7
    assert result4 == 7
    assert counter.call_count == 3

    result1 = await StaticMethod.static_add(a=4, b=5)
    result2 = await StaticMethod.static_add(a=4, b=5)  # Should hit
    result3 = await StaticMethod.static_add(0, b=4)  # Should hit
    result4 = await StaticMethod.static_add(1, b=4)  # Should hit
    assert result1 == 9
    assert result2 == 9
    assert result3 == 4
    assert result4 == 5
    assert StaticMethod.call_count == 3

    counter = ClassMethod()
    result1 = await counter.class_add(5, 1)
    result2 = await counter.class_add(5, 2)  # Should hit cache, since 'b' is ignored
    result3 = await counter.class_add(6, 1)  # Should miss cache
    result4 = await counter.class_add(5, 1)  # Should miss cache
    assert result1 == 6
    assert result2 == 6
    assert result3 == 7
    assert result4 == 6
    assert ClassMethod.call_count == 3


if __name__ == "__main__":
    asyncio.run(main())
