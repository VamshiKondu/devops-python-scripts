# aiocachetools

**aiocachetools** is a high-performance, asynchronous caching library for Python. It provides decorators for caching results of coroutine functions and methods, specifically designed to handle the "thundering herd" (cache stampede) problem in high-concurrency environments.

This project is inspired by and references [imnotjames/cachetools-async](https://github.com/imnotjames/cachetools-async). It builds upon that foundation by adding specialized logic to **ignore specific parameters** from cache key generation, providing more granular control over cache hits.

---

## ✨ Key Features

* **Concurrency-Safe**: Caches the `asyncio.Future` rather than the result. Concurrent calls for the same key wait for a single task, preventing redundant executions.
* **Decorator Support**: Easy `@cached` and `@cachedmethod` implementations.
* **Parameter Filtering**: Supports an `ignore` parameter to exclude specific arguments (e.g., `self`, `cls`, `db_session`) from the cache key.
* **Modern Logging**: Uses [Loguru](https://github.com/Delgan/loguru) for internal state reporting (hits/misses) at the `DEBUG` level.

---

## 📦 Installation

This project is managed with [uv](https://github.com/astral-sh/uv). To set up the environment and install all dependencies:

```bash
# Sync the environment and install all dependency groups
uv sync --all-groups

# Recommended: Install in editable mode to resolve import paths for testing
uv pip install -e .

```

---

## 🛠 Usage

### 1. Basic Function Caching

Use `@cached` for standalone coroutines.

```python
from cachetools import TTLCache
from aiocachetools import cached

cache = TTLCache(maxsize=10, ttl=60)

@cached(cache=cache)
async def fetch_api_data(user_id: int):
    return {"user": user_id, "status": "active"}

```

### 2. Instance Method Caching (`test_instance_method_cache`)

Standard usage where each instance has its own private cache.

```python
class UserService:
    def __init__(self):
        self.cache = TLRUCache(maxsize=100, ttu=lambda k, v, t: t + 300)

    @cachedmethod(cache=lambda self: self.cache)
    async def get_user_profile(self, user_id: str):
        return await fetch_from_db(user_id)

```

### 3. Class Method Caching (`test_classmethod_cache`)

Useful for singleton-style services where the cache is shared across the class. **Note:** Use `ignore=("cls",)` so the class object itself doesn't affect the cache key.

```python
class GlobalConfig:
    _cache = TLRUCache(maxsize=10, ttu=lambda k, v, t: t + 600)

    @cachedmethod(cache=lambda cls: cls._cache, ignore=("cls",))
    @classmethod
    async def get_setting(cls, key: str):
        return await load_setting(key)

```

### 4. Static-Like Method Caching (`test_cachemethod_staticmethod`)

If a method is functionally static but you want it to use an instance-bound cache, use `ignore=("self",)`.

```python
class MathOps:
    call_count = 0

    @staticmethod
    @cached(cache=TLRUCache(maxsize=10, ttu=lambda k, v, t: t + 10))
    async def static_multiply(a: int, b: int) -> int:
        MathOps.call_count += 1
        await asyncio.sleep(0.1)
        return a * b

```

---

## 🧪 Development & Testing

### Running Tests

To ensure the project structure and imports are recognized correctly, use `uv run`:

```bash
uv run pytest -s -v test/test_async_cache.py

```

### Troubleshooting Imports

If you encounter a `ModuleNotFoundError: No module named 'async_cache'`, ensure you have performed an **editable install**:

```bash
uv pip install -e .

```

---

## 📜 Credits

* Core async patterns referenced from [imnotjames/cachetools-async](https://github.com/imnotjames/cachetools-async).
* Parameter ignoring logic and Loguru integration enhancements by the current contributor.
