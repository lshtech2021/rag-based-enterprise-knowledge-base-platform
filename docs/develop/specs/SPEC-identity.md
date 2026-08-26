# Spec: identity

Module id: `identity`  
Depends on: `platform-foundation`  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)

---

## Objective

Authenticate API callers at the BFF and enforce simple RBAC so protected routes (e.g. `/v1/query`) know **who** is asking and **whether** they are allowed—without blocking the approved **dev auth bypass** path.

**Users:** analysts (query/report), operators (ingestion), admins (future).

**MVP success:**  
- `AUTH_MODE=dev_bypass` (default): requests succeed without a token; principal is a well-known dev user with role `analyst`.  
- `AUTH_MODE=oidc`: `Authorization: Bearer <JWT>` required; invalid/missing token → 401; wrong role → 403.  
- `GET /v1/me` returns the current principal.  
- No live Keycloak/Auth0 required for tests (HMAC JWT stand-in behind `TokenValidatorPort`).

---

## Tech Stack

| Piece | Choice |
|---|---|
| Package | `kb-identity` in `packages/identity` |
| API | FastAPI dependencies on BFF |
| JWT (test/OIDC stand-in) | PyJWT HS256 with configurable secret |
| Real OIDC JWKS | Port only; Keycloak/Auth0 adapter deferred (ask first) |

---

## Commands

```bash
uv sync --group dev
uv run pytest packages/identity apps/bff -q
make test lint typecheck
```

---

## Project Structure

```
packages/identity/
  src/kb_identity/
    domain/principal.py
    application/ports.py
    application/authenticate.py
    infrastructure/dev_bypass.py
    infrastructure/hmac_jwt.py
    infrastructure/factory.py
  tests/
apps/bff/
  auth_deps.py          # FastAPI require_principal / require_roles
  identity_router.py    # GET /v1/me
```

---

## Testing Strategy

- Unit: role checks; HMAC JWT accept/reject; dev bypass principal
- BFF: `/v1/me` in bypass mode; `/v1/query` 401 without token when `oidc`; 200 with valid analyst JWT

---

## Boundaries

**Always:** Default `dev_bypass`; never commit real OIDC client secrets; include `auth_mode` on `/healthz`.

**Ask first:** Adding Auth0/Keycloak as required runtime; changing role names once UI depends on them.

**Never:** Trust unsigned tokens in `oidc` mode; log raw bearer tokens.

---

## Success Criteria

1. Dev bypass: `/v1/me` → `user_id=dev-user`, roles include `analyst`.
2. OIDC mode without header → 401 on `/v1/query` and `/v1/me`.
3. Valid HS256 JWT with role `analyst` → `/v1/me` 200 and query allowed.
4. JWT with only unrelated role → 403 on `/v1/query`.
5. `make test lint typecheck` green offline.

---

## Open Questions

Prefer Auth0 vs Keycloak when wiring real OIDC — deferred until frontend SSO.
