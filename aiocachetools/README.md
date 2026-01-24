**aiocachetools** is a high-performance, asynchronous caching library for Python. It provides decorators for caching results of coroutine functions and methods, specifically designed to handle the "thundering herd" (cache stampede) problem in high-concurrency environments.

This project is inspired by and references [imnotjames/cachetools-async](https://github.com/imnotjames/cachetools-async). It builds upon that foundation by adding specialized logic to **ignore specific parameters** from cache key generation, providing more granular control over cache hits.

---

## ✨ Key Features

* **Concurrency-Safe**: Caches the `asyncio.Future` rather than the result. Concurrent calls for the same key wait for a single task, preventing redundant executions.
* **Decorator Support**: Easy `@cached` and `@cachedmethod` implementations.
* **Parameter Filtering**: Supports an `ignore` parameter to exclude specific arguments (e.g., `self`, `cls`, `db_session`) from the cache key.
* **Professional Logging**: Uses Python's standard `logging` module. Internal state (hits/misses) is reported at the `DEBUG` level for easy troubleshooting without console clutter.

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
import asyncio
from cachetools import TTLCache
from aiocachetools import cached

cache = TTLCache(maxsize=10, ttl=60)

@cached(cache=cache)
async def fetch_api_data(user_id: int):
    await asyncio.sleep(0.5)
    return {"user": user_id, "status": "active"}

```

### 2. Ignoring Parameters

Exclude specific arguments that shouldn't affect the cache result (like database sessions or loggers).

```python
# 'db' will be ignored; only 'user_id' generates the key
@cached(cache=cache, ignore=("db",))
async def get_user(user_id: int, db: Any):
    return await db.fetch_user(user_id)

```

---

## 🧪 Development & Testing

### Running Tests

To ensure the project structure is recognized correctly, always use `uv run`:

```bash
uv run pytest -s -v test/test_async_cache.py

```

### Troubleshooting Imports

If you encounter a `ModuleNotFoundError: No module named 'async_cache'`, ensure you have performed an **editable install** in your environment:

```bash
uv pip install -e .

```

This allows `pytest` to find the `async_cache` module regardless of your current working directory.

---

## 📜 Credits

* Core async patterns referenced from [imnotjames/cachetools-async](https://github.com/imnotjames/cachetools-async).
* Parameter ignoring logic, professional logging enhancements by the current contributor.