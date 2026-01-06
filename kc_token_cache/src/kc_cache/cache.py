from __future__ import annotations
from cachetools import TLRUCache
from typing import Optional, Dict, Any, Callable
import time
import logging

from kc_token_cache.src.kc_cache.utils import decode_jwt_payload

logger = logging.getLogger(__name__)

TTUCallable = Callable[[str, Any, float], float]


def default_jwt_exp_ttu(key: str, value: Any, now: float) -> float:
    """
    Default ttu function that expects `value` to be the dict we store in the cache:
    {
        "token": "<jwt>",
        "payload": {...} (optional),
        "expires_at": <ts> (optional),
        "refresh_token": "..." (optional)
    }
    Returns absolute timestamp (epoch seconds) when the entry should no longer be used.
    Falls back to now + 3600 on error/missing exp.
    """
    try:
        # if we already precomputed expires_at, use it
        if isinstance(value, dict):
            expires_at = value.get("expires_at")
            if expires_at:
                try:
                    return float(expires_at)
                except Exception:
                    pass
            token = value.get("token")
        else:
            # value could be raw token string in some usages
            token = value

        if not token:
            logger.warning(
                f"No token found in cache value for key {key}, using default TTL"
            )
            return now + 3600.0

        payload = decode_jwt_payload(token)
        exp = payload.get("exp")
        if exp:
            # exp may be int (unix epoch), return as float epoch
            return float(exp)
        logger.warning(
            f"No exp claim found in JWT token for key {key}, using default TTL"
        )
        return now + 3600.0
    except Exception as e:
        logger.error(f"Error parsing JWT token for key {key}: {e}")
        return now + 3600.0


class TokenCache:
    """
    Lightweight wrapper around cachetools.TLRUCache that stores entries with explicit expires_at.
    Each value stored is a dict:
    {
        "token": "...",
        "payload": {...},
        "expires_at": unix_ts,
        "refresh_token": "..." (optional)
    }

    The constructor accepts an optional `ttu` callable (key, value, now) -> absolute timestamp,
    and passes it to TLRUCache.
    """

    def __init__(self, maxsize: int = 1024, ttu: Optional[TTUCallable] = None):
        try:
            # If ttu provided, pass it to TLRUCache; else use default_jwt_exp_ttu
            ttu_to_use = ttu if ttu is not None else default_jwt_exp_ttu
            # TLRUCache expects signature (maxsize, ttu=None, timer=time.time, getsizeof=None)
            self._cache = TLRUCache(maxsize=maxsize, ttu=ttu_to_use)
        except TypeError:
            # In case running with a cachetools version that doesn't accept ttu,
            # fall back to constructing with only maxsize and warn.
            logger.warning(
                "TLRUCache does not accept ttu parameter in this cachetools version; building without ttu"
            )
            self._cache = TLRUCache(maxsize=maxsize)
        except Exception as exc:
            # if TLRUCache signature changed in another way, surface a clear error
            raise RuntimeError(
                "Unable to initialize TLRUCache from cachetools."
            ) from exc

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if not entry:
            return None
        expires_at = entry.get("expires_at")
        if expires_at and expires_at <= int(time.time()):
            # expired: evict and return None
            try:
                del self._cache[key]
            except KeyError:
                pass
            return None
        return entry

    def set(self, key: str, value: Dict[str, Any]) -> None:
        self._cache[key] = value

    def delete(self, key: str) -> None:
        try:
            del self._cache[key]
        except KeyError:
            pass

    def keys(self):
        return list(self._cache.keys())

    def raw_cache(self):
        # for inspection/debug (avoid printing secrets)
        return self._cache
