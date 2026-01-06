from __future__ import annotations
import os
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import yaml
import re

_ENV_RE = re.compile(r"\$\{([^}]+)\}")


def _sub_env_vars(s: str) -> str:
    # Replace ${VAR} with env var value, error if missing
    def repl(m):
        name = m.group(1)
        val = os.environ.get(name)
        if val is None:
            raise EnvironmentError(
                f"Environment variable {name} required by config but not set"
            )
        return val

    return _ENV_RE.sub(repl, s)


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    # perform simple env substitution for known patterns ${VAR}
    raw = _ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), raw)
    if path.endswith((".yaml", ".yml")):
        return yaml.safe_load(raw)
    elif path.endswith(".json"):
        return json.loads(raw)
    else:
        # try YAML first, fallback to JSON
        try:
            return yaml.safe_load(raw)
        except Exception:
            return json.loads(raw)


@dataclass
class TokenConfig:
    token_url: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    grant_type: str = "client_credentials"
    username: Optional[str] = None
    password: Optional[str] = None
    scope: Optional[str] = None
    audience: Optional[str] = None
    fallback_ttl_seconds: Optional[int] = None
    prefetch_seconds: int = 30
    verify_tls: bool = True

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "TokenConfig":
        if not d:
            raise ValueError("TokenConfig requires a mapping")
        processed = {}
        for k, v in d.items():
            if isinstance(v, str) and "${" in v:
                processed[k] = _sub_env_vars(v)
            else:
                processed[k] = v
        return TokenConfig(**processed)


@dataclass
class KeycloakEntry:
    name: str
    access: TokenConfig
    refresh: Optional[TokenConfig] = None
    enabled: bool = True
    cache: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "KeycloakEntry":
        if "name" not in d:
            raise ValueError("Keycloak entry must have a 'name'")
        access = TokenConfig.from_dict(d["access"])
        refresh = None
        if d.get("refresh"):
            refresh = TokenConfig.from_dict(d["refresh"])
        return KeycloakEntry(
            name=d["name"],
            access=access,
            refresh=refresh,
            enabled=d.get("enabled", True),
            cache=d.get("cache", {}),
        )


def parse_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    entries = [KeycloakEntry.from_dict(e) for e in raw.get("keycloaks", [])]
    cfg["keycloaks"] = {e.name: e for e in entries}
    cfg["cache"] = raw.get("cache", {})
    return cfg
