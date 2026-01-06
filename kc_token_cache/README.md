# Keycloak Token Cache (Python, TLRUCache)

Simple utility to cache Keycloak tokens for multiple Keycloak configurations using `cachetools.TLRUCache`.

Requirements
- Python 3.8+
- Install: `pip install -r requirements.txt`

Files
- `src/kc_cache/config.py` — config dataclasses and loader (YAML/JSON + env substitution)
- `src/kc_cache/utils.py` — helpers and JWT payload decoder
- `src/kc_cache/cache.py` — TLRUCache wrapper for token entries
- `src/kc_cache/client.py` — KeycloakTokenManager: fetch, cache, refresh tokens
- `scripts/kc_cache_cli.py` — CLI: get / refresh / list tokens

Usage examples
- Load config and get an access token:
  `python scripts/kc_cache_cli.py --config config.yaml get kc-main access`
- Force refresh:
  `python scripts/kc_cache_cli.py --config config.yaml refresh kc-main access`
- List configured keycloaks:
  `python scripts/kc_cache_cli.py --config config.yaml list`

Config example (YAML)
```yaml
keycloaks:
  - name: kc-main
    access:
      token_url: "https://auth.example.com/realms/main/protocol/openid-connect/token"
      client_id: "svc-client"
      client_secret: "${KC_MAIN_ACCESS_CLIENT_SECRET}"
      grant_type: "client_credentials"
      fallback_ttl_seconds: 300
      prefetch_seconds: 30
    refresh:
      token_url: "https://auth.example.com/realms/main/protocol/openid-connect/token"
      client_id: "svc-client"
      client_secret: "${KC_MAIN_REFRESH_CLIENT_SECRET}"
      grant_type: "refresh_token"
cache:
  backend: "tlru"
  maxsize: 1024
```

Security notes
- Do not commit client secrets in config; prefer environment variables or secret stores.
- The code avoids logging secrets.