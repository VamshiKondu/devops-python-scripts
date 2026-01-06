#!/usr/bin/env python3
"""
Minimal provider-based helper for retrieving access tokens.

Behavior:
- No argparse. This module exposes simple functions to load the config
  and get an access token (async and sync).
- When executed as a script it expects at least one argument: the path to the YAML/JSON config.
  Optionally a second argument can be provided to override the configured default keycloak name.
  Example:
    python scripts/kc_cache_cli.py config.yaml
    python scripts/kc_cache_cli.py config.yaml kc-main

Programmatic usage:
    from scripts.kc_cache_cli import get_access_token
    token = get_access_token("config.yaml", name="kc-main")
"""
import sys
import asyncio
import logging
from typing import Optional, Dict, Any

from src.kc_cache.provider import TokenProvider

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kc_cache_cli")


async def get_access_token_async(config_path: str, name: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Async helper that loads provider from config_path and returns token info dict for `name`
    (if name is None uses the configured default in the YAML).
    Returned dict contains at least: token, payload, expires_at
    """
    provider = TokenProvider(config_path)
    return await provider.get_token(name=name, token_type="access", force_refresh=force_refresh)


def get_access_token(config_path: str, name: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Synchronous wrapper around get_access_token_async.
    Returns the same dict as the async function.
    """
    return asyncio.run(get_access_token_async(config_path=config_path, name=name, force_refresh=force_refresh))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: kc_cache_cli.py <config_path> [name]")
        sys.exit(2)

    cfg_path = sys.argv[1]
    name_arg = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        info = get_access_token(cfg_path, name=name_arg, force_refresh=False)
        # print only the token string for CLI friendliness
        print(info["token"])
    except Exception as e:
        log.error("Failed to obtain token: %s", e)
        sys.exit(1)