"""
Simple async HTTP service (FastAPI) exposing token operations.
Run with: uvicorn scripts.kc_cache_service:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from typing import Dict, Any
from src.kc_cache.config import load_config, parse_config
from src.kc_cache.client import KeycloakTokenManager, default_jwt_exp_ttu

# Load config at startup (could be provided via env var)
CONFIG_PATH = "config.yaml"

app = FastAPI(title="Keycloak Token Cache Service")

class TokenResponse(BaseModel):
    token: str
    payload: Dict[str, Any] = None
    expires_at: int

@app.on_event("startup")
async def startup_event():
    raw = load_config(CONFIG_PATH)
    cfg = parse_config(raw)
    cache_cfg = cfg.get("cache", {}) or {}
    cache_max = cache_cfg.get("maxsize", 1024)
    cache_ttu_cfg = cache_cfg.get("ttu")
    if cache_ttu_cfg == "jwt_exp":
        cache_ttu = default_jwt_exp_ttu
    else:
        cache_ttu = None
    # attach manager to app state (pass ttu through)
    app.state.kc_manager = KeycloakTokenManager(cfg, cache_maxsize=cache_max, cache_ttu=cache_ttu)

@app.get("/tokens", response_model=Dict[str, Any])
async def list_tokens():
    return app.state.kc_manager.list_entries()

@app.get("/tokens/{name}/{token_type}", response_model=TokenResponse)
async def get_token(name: str, token_type: str):
    try:
        info = await app.state.kc_manager.get_token(name, token_type)
        return {
            "token": info["token"],
            "payload": info.get("payload"),
            "expires_at": info.get("expires_at"),
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Keycloak entry not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tokens/{name}/{token_type}/refresh", response_model=TokenResponse)
async def refresh_token(name: str, token_type: str):
    try:
        info = await app.state.kc_manager.get_token(name, token_type, force_refresh=True)
        return {
            "token": info["token"],
            "payload": info.get("payload"),
            "expires_at": info.get("expires_at"),
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Keycloak entry not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))