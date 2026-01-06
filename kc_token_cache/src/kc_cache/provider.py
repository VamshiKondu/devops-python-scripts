from __future__ import annotations
import asyncio
import logging
from typing import Optional, Dict, Any
from kc_token_cache.src.kc_cache.config import load_config, parse_config
from kc_token_cache.src.kc_cache.client import KeycloakTokenManager

logger = logging.getLogger(__name__)


class TokenProvider:
    """
    High-level helper that loads the YAML/JSON config and exposes methods to
    obtain tokens by the configured name. If no name is supplied to get_token,
    the provider will use the `default_keycloak` value from the config file if present,
    otherwise it will use the first configured keycloak entry.

    Usage (programmatic async):
        provider = TokenProvider("config.yaml")
        token_info = await provider.get_token()  # uses default keycloak
        token_info = await provider.get_token(name="kc-main")

    Usage (sync convenience):
        provider = TokenProvider("config.yaml")
        token = provider.get_token_sync()  # returns token string
    """

    def __init__(self, config_path: str, cache_ttu: Optional[Any] = None):
        """
        config_path: path to YAML/JSON config
        cache_ttu: either None, "jwt_exp", or a callable (key, value, now) -> float
                  If None, will default to built-in behavior (jwt exp extractor).
        """
        raw = load_config(config_path)
        parsed = parse_config(raw)
        self._raw = raw
        self._cfg = parsed
        keycloaks = parsed.get("keycloaks", {}) or {}
        if not keycloaks:
            raise RuntimeError("No keycloak entries found in config")

        # determine default name: prefer explicit default_keycloak, else first entry
        default_name = (
            raw.get("default_keycloak")
            or raw.get("default")
            or next(iter(keycloaks.keys()))
        )
        self.default_name: str = default_name

        cache_cfg = parsed.get("cache", {}) or {}
        cache_max = cache_cfg.get("maxsize", 1024)
        # determine ttu to pass through: if config has "ttu" == "jwt_exp" use builtin
        cfg_ttu = cache_cfg.get("ttu")
        if cache_ttu is not None:
            # explicit programmatic override
            ttu_to_pass = cache_ttu
        elif cfg_ttu == "jwt_exp" or cfg_ttu is None:
            # None or "jwt_exp" => use builtin default_jwt_exp_ttu
            ttu_to_pass = "jwt_exp"
        else:
            # unknown string or value; do not pass callable here (client will handle)
            ttu_to_pass = None

        self._manager = KeycloakTokenManager(
            self._cfg, cache_maxsize=cache_max, cache_ttu=ttu_to_pass
        )

    async def get_token(
        self,
        name: Optional[str] = None,
        token_type: str = "access",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Return the token info dict for the configured (or provided) name.

        Returned dict contains at least: token, payload, expires_at
        """
        target = name or self.default_name
        if target not in self._cfg.get("keycloaks", {}):
            # help the caller with available names
            available = ", ".join(self._cfg.get("keycloaks", {}).keys())
            raise KeyError(f"Unknown keycloak name: {target}. Available: {available}")
        return await self._manager.get_token(target, token_type, force_refresh)

    def get_token_sync(
        self,
        name: Optional[str] = None,
        token_type: str = "access",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for convenience (uses asyncio.run).
        Returns the same dict as the async get_token.
        """
        return asyncio.run(
            self.get_token(
                name=name, token_type=token_type, force_refresh=force_refresh
            )
        )
