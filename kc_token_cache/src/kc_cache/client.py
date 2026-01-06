from __future__ import annotations
from typing import Optional, Dict, Any, Callable
import httpx
import logging

from kc_token_cache.src.kc_cache.config import KeycloakEntry, TokenConfig
from kc_token_cache.src.kc_cache.utils import decode_jwt_payload, now_ts
from kc_token_cache.src.kc_cache.cache import TokenCache, default_jwt_exp_ttu

logger = logging.getLogger("kc_cache")
# do not configure logging here; let the exposing app configure logging

TTUCallable = Callable[[str, Any, float], float]


class KeycloakTokenManager:
    def __init__(
        self,
        config: Dict[str, Any],
        cache_maxsize: int = 1024,
        cache_ttu: Optional[TTUCallable] = None,
        client_limits: Optional[Dict[str, Any]] = None,
    ):
        """
        config: parsed config dict from parse_config(load_config(...))
        cache_maxsize: passed to TokenCache / TLRUCache
        cache_ttu: optional ttu callable passed to TLRUCache; if the string "jwt_exp" is desired,
                   pass the builtin default_jwt_exp_ttu (or set cache_ttu to default by passing None).
        """
        self.cfg = config
        self.entries: Dict[str, KeycloakEntry] = config.get("keycloaks", {})
        # If cache_ttu is exactly the string "jwt_exp" (legacy config), use builtin
        ttu_to_use = None
        if cache_ttu == "jwt_exp":
            ttu_to_use = default_jwt_exp_ttu
        elif callable(cache_ttu):
            ttu_to_use = cache_ttu
        else:
            # None means TokenCache will use its default_jwt_exp_ttu
            ttu_to_use = None

        # Pass both maxsize and ttu through to TokenCache
        self.cache = TokenCache(maxsize=cache_maxsize, ttu=ttu_to_use)
        # Optional shared AsyncClient instance could be created, but we'll create per-call clients to keep simple.
        self._client_limits = client_limits or {}

    @staticmethod
    def _compute_expires_at(
        token: str, expires_in: Optional[int], fallback: Optional[int]
    ) -> int:
        now = now_ts()
        if expires_in:
            try:
                return now + int(expires_in)
            except Exception:
                pass
        # try exp claim
        try:
            payload = decode_jwt_payload(token)
            exp = payload.get("exp")
            if exp:
                return int(exp)
        except Exception:
            pass
        # fallback
        if fallback:
            return now + int(fallback)
        # default: 60 seconds
        return now + 60

    async def _fetch_token(
        self, cfg: TokenConfig, extra: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        data = {"grant_type": cfg.grant_type}
        if cfg.grant_type == "client_credentials":
            if cfg.client_id:
                data["client_id"] = cfg.client_id
            if cfg.client_secret:
                data["client_secret"] = cfg.client_secret
        elif cfg.grant_type == "password":
            if not (cfg.username and cfg.password):
                raise ValueError("password grant requires username and password")
            data["username"] = cfg.username
            data["password"] = cfg.password
            if cfg.client_id:
                data["client_id"] = cfg.client_id
            if cfg.client_secret:
                data["client_secret"] = cfg.client_secret
        elif cfg.grant_type == "refresh_token":
            # requires a refresh_token in extra
            if not extra or "refresh_token" not in extra:
                raise ValueError("refresh_token grant requires existing refresh_token")
            data["refresh_token"] = extra["refresh_token"]
            if cfg.client_id:
                data["client_id"] = cfg.client_id
            if cfg.client_secret:
                data["client_secret"] = cfg.client_secret
        else:
            # allow passing arbitrary fields via extra
            if extra:
                data.update(extra)

        if cfg.scope:
            data["scope"] = cfg.scope
        if cfg.audience:
            data["audience"] = cfg.audience

        # Use httpx.AsyncClient to perform the POST
        # honor cfg.verify_tls by passing verify flag
        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient(timeout=timeout, verify=cfg.verify_tls) as client:
            resp = await client.post(cfg.token_url, data=data)
            resp.raise_for_status()
            return resp.json()

    async def get_token(
        self, name: str, token_type: str = "access", force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Return dict with keys: token, payload, expires_at, refresh_token (optional)
        token_type: "access" or "refresh"
        """
        if name not in self.entries:
            raise KeyError(f"Unknown keycloak name: {name}")
        entry = self.entries[name]
        if not entry.enabled:
            raise RuntimeError(f"Keycloak entry {name} is disabled")

        key = f"{name}:{token_type}"
        cached = None if force_refresh else self.cache.get(key)
        if cached:
            # check prefetch window
            prefetch = getattr(entry.access, "prefetch_seconds", 30)
            expires_at = cached.get("expires_at")
            if expires_at and expires_at - now_ts() <= prefetch:
                # proactively refresh
                cached = None

        if cached:
            # do not return refresh_token unless requested
            if token_type == "access":
                return {k: v for k, v in cached.items() if k != "refresh_token"}
            return cached

        # need to fetch
        cfg = (
            entry.access if token_type == "access" else (entry.refresh or entry.access)
        )
        extra = {}
        # if refreshing access using refresh token, attempt to supply stored refresh_token
        if token_type == "access" and entry.refresh:
            # try to find stored refresh token
            rt_key = f"{name}:refresh"
            rt_cached = self.cache.get(rt_key)
            if rt_cached and rt_cached.get("refresh_token"):
                extra["refresh_token"] = rt_cached["refresh_token"]

        resp = await self._fetch_token(cfg, extra or None)
        access_token = resp.get("access_token") or resp.get(
            "id_token"
        )  # sometimes id_token returned
        refresh_token = resp.get("refresh_token")
        expires_in = resp.get("expires_in")
        if not access_token:
            raise RuntimeError("Token endpoint did not return access_token/id_token")

        # compute expires_at
        expires_at = self._compute_expires_at(
            access_token, expires_in, cfg.fallback_ttl_seconds
        )
        # store in cache
        cache_value = {
            "token": access_token,
            "payload": None,
            "expires_at": expires_at,
        }
        try:
            cache_value["payload"] = decode_jwt_payload(access_token)
        except Exception:
            cache_value["payload"] = None
        if refresh_token:
            cache_value["refresh_token"] = refresh_token
            # store refresh token separately with same expiry (or compute if needed)
            self.cache.set(
                f"{name}:refresh",
                {
                    "token": refresh_token,
                    "payload": None,
                    "expires_at": expires_at,
                    "refresh_token": refresh_token,
                },
            )
        # set cache entry for requested type
        self.cache.set(f"{name}:{token_type}", cache_value)
        result = {k: v for k, v in cache_value.items() if k != "refresh_token"}
        return result

    def list_entries(self) -> Dict[str, Any]:
        return {name: {"enabled": e.enabled} for name, e in self.entries.items()}
