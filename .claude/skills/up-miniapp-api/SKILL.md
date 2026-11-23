---
name: up-miniapp-api
description: Backend guide for api/. MVC by default, Hub token checks, public/authenticated/admin routes, configuration and secrets, errors, CORS, data (PostgreSQL, cache, bucket), calling the Hub, tests and the production Dockerfile. Use before writing or reviewing any code under api/, and for any security question about the API.
---

# Up mini-app API

How to use this skill:
- `api/AGENT.md` holds the rules. This skill shows how to apply them.
- Copy the patterns of this repository. Do not invent a new one.

## 1. Stack and commands

- Python 3.14, FastAPI, Pydantic v2, PyJWT.
- Packages: `uv` only. Never `pip` or `requirements.txt`.
- Quality: ruff (lint and format), `mypy --strict`, pytest.

```bash
uv sync
uv run --env-file .env python -m app        # 127.0.0.1:21514, docs on /docs
uv lock --check && uv run ruff format . && uv run ruff check . && uv run mypy app tests && uv run pytest
```

## 2. Architecture: MVC by default

Every backend of a mini-app uses MVC by default, with a service layer between the controller and the model. Keep this shape unless the user asks for another one.

| MVC part | Folder | Holds |
| --- | --- | --- |
| Model | `app/models/` (ORM entities) and `app/repositories/` (database access) | The data and how it is stored. Created with the first table. |
| View | `app/schemas/` | The Pydantic models of the JSON responses and requests. No HTML templates: the view is the JSON contract. |
| Controller | `app/api/routes/` | One module per resource. Parse the input, call a service, return a schema. |
| Service | `app/services/` | The business rules. Plain Python, no HTTP. |

Flow of a request: controller, then service, then repository, then model. The answer goes back as a view (schema). A controller never calls a repository. A repository returns domain objects, never the ORM session. The controller returns a schema.

Files of this repository:

```text
app/
├── main.py           create_app(config): the factory, no global app
├── api/router.py     mounts routers under /api/v1
├── api/deps.py       the ONLY place routes get collaborators (services, current user)
├── api/routes/       one module per resource: parse, delegate, return
├── core/config.py    typed config (TOML + environment)
├── core/security.py  verification of the Hub's user tokens
├── core/errors.py    AppError hierarchy and handlers
├── schemas/          Pydantic models, camelCase on the wire (CamelModel)
└── services/         business logic, plain Python, no HTTP
```

Rules:
- Dependencies go one way: `routes -> services -> (repositories, schemas, core)`. `repositories` exists once the first table does.
- A service never imports `api/`. A route holds no business rule.
- Add `models/` and `repositories/` with the first table. Add `services/hub_client.py` with the first Hub call. Not before.

Adding an endpoint:
1. `schemas/<resource>.py`: request and response models (`CamelModel`).
2. `services/<resource>_service.py`: small typed methods. Expected failures raise an `AppError` subclass.
3. `api/deps.py`: `get_<resource>_service` and an `Annotated` alias.
4. `api/routes/<resource>.py`: thin function, typed return, `summary`, constrained inputs.
5. Mount it in `api/router.py`.
6. `tests/test_<resource>.py`: success, validation failure (422), auth failure (401), and 403 for an admin route.

## 3. Authentication: the Hub's token

1. The shell asks the Hub for a scoped token. It is an ES256 JWT:
   - `sub`: the user uuid;
   - `aud`: this mini-app's uuid;
   - `scp`: `["profile:miniapp:admin"]` for a user with the global Hub flag `miniapp_admin`, absent or empty otherwise;
   - `exp`: a short expiry.
2. The shell sends it as `Authorization: Bearer <token>`.
3. `core/security.py` verifies it offline with the Hub's **public** key.

What `TokenVerifier.verify` enforces (keep all of it):
- `algorithms=["ES256"]`: the token's own `alg` is never trusted.
- `audience=[app_uuid]`: a token of another mini-app is refused.
- `require: exp, sub, aud`.
- `scp` may be absent. When present it must be a list of strings.
- On failure: log the reason type, never the token. Answer `401`.

In `development` only, the API also accepts the audience `99999999-9999-9999-9999-999999999999`. It is the shell's "Vite Dev" entry.

In `production` the API refuses to start on the DEV mock registration (`0d0d0d0d-0000-4000-8000-000000000001` / `mock_secret`).

## 4. Access levels

Pick one for every route before writing it. User data is never public.

| Level | Dependency | Example |
| --- | --- | --- |
| Public | none | `GET /api/v1/hello`, `GET /healthz` |
| Authenticated | `CurrentUserDep` | `GET /api/v1/me` |
| Admin | `require_admin`, on the `/admin` router | `GET /api/v1/admin/hello` |

```python
# api/routes/admin.py: the guard sits on the router, no admin route can forget it
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
```

Rules:
- Admin means the scope `profile:miniapp:admin` is in the signed token.
- The Hub adds it on its own when the user has the global Hub flag `miniapp_admin`. The flag is valid for every mini-app, not a per-app grant. Nobody asks for it: the Hub ignores a `scopes` field in the token request.
- A token made in the Studio tab "Scope tokens" (`POST /admin/applications/{uuid}/token`, by an organisation admin or a super user) always carries it.
- The token of any other user has no `scp` claim.
- A mini-app declares no scopes. It gets the whole user profile from the shell.
- Never keep a list of admins in this API. Never trust an admin flag from the client.
- `401` = no or invalid token. `403` = valid token without the right.
- The user is `user.user_uuid` from the token. Never trust a user id sent in a body, header or query.
- Check ownership in the service. A user reads and changes only their own rows. Only an admin route may do more.
- Admin routes return only what is needed.
- Each admin route has three tests: admin 200, user 403, anonymous 401.

## 5. Configuration and secrets

- `configs/config.toml` lists every key with safe defaults and empty placeholders for secrets.
- The environment overrides a key: dotted key, upper-cased, dots to underscores. `hub.base_url` becomes `HUB_BASE_URL`.
- `environment` is a top-level key. Its variable is `ENVIRONMENT`.
- Read once through `get_config()`. Nothing else reads `os.environ`.
- Secrets are `SecretStr`. Read them with `.get_secret_value()` only where they are used.
- `api/.env` is written by the workspace and gitignored. Never commit it, print it or copy its values.
- In production the platform sets `HUB_APP_UUID` and `HUB_CLIENT_SECRET`. It mounts the Hub key.
- In production the platform also sets `DATABASE_URL`, `CACHE_URL`, `CACHE_KEY_PREFIX` and `STORAGE_*`, for the services enabled in `miniapp.yaml`.
- A new setting: key in `config.toml`, field in `core/config.py`, test in `tests/test_config.py`.

## 6. Errors

- Raise an `AppError` subclass: `UnauthorizedError`, `ForbiddenError`, `ServiceUnavailableError`.
- A new failure class gets a new subclass, with its `status_code` and `code`.
- Body is always `{"error": {"code", "message"}}`. Messages are safe for the client.
- Unexpected exceptions become `500 internal_error`. The traceback goes to the logs only.
- Catch the narrowest exception. Add context. Re-raise with `from`. Never `except Exception: pass`.
- Log with `logging.getLogger(__name__)` and `extra`. Never `print`, never a token, secret or personal data.

## 7. Hardening already in place (keep it)

- `/docs` and `/openapi.json` are off when `environment = "production"` (`tests/test_hardening.py`).
- CORS is an allow-list (`cors.allowed_origins`). Local origins are allowed in development only. Never `*`.
- `allow_methods` is `["GET"]`. Add a method only when a route needs it.
- Validation in the types: `Query(min_length=..., max_length=..., pattern=...)`, `Field(...)`. Reject, never sanitise silently.

## 8. Data

- **PostgreSQL**: `config.database.url`. Parameters or a query builder only. Never string-built SQL.
- **Cache** (Valkey, Redis protocol): every key and channel starts with `config.cache.key_prefix`. The cache user can touch nothing else and cannot `SCAN` or `KEYS`.
- **Bucket** (S3): `config.storage.bucket` only. Never trust an object key sent by the client. Build it from the user uuid and a generated name.
- These DEV resources are shared by all members of the mini-app. Never put real personal data in them.
- `GET /api/v1/resources` (authenticated) checks that each one answers.

## 9. Calling the Hub (machine to machine)

Only for Hub features (points, push, achievements):

```text
POST {hub.base_url}/partner/auth/login   {"appUuid": "...", "clientSecret": "..."}
-> {"token": "<M2M JWT>", "expiresAt": 86400}
```

- Put it in `services/hub_client.py`: one class, with an injectable `httpx2` client.
- Set a timeout on every call.
- Cache the token. Refresh it a few minutes before expiry.
- Some partner features must be allow-listed for the app uuid. Ask the Up team. Never work around it.

## 10. Tests

- Use `TestClient(create_app(test_config))`. Prefer the real app over mocks. Fake only the Hub.
- `tests/conftest.py` signs tokens with a local key pair standing in for the Hub. `make_token(audience=...)` builds variants.
- Cover: success, 422, 401, 403, a token with the wrong `aud`, an expired token.

## 11. Production image (`api/Dockerfile`)

- Multi-stage build with `uv sync --frozen --no-dev`.
- Pinned base images. Non-root user `10001`. `/app` read-only.
- `ENVIRONMENT=production` and `SERVER_HOST=0.0.0.0`.
- `SERVER_PORT` comes from the build argument `API_PORT`, which is `api.port` of `miniapp.yaml` (1024 or more).
- No secret in the image. `.dockerignore` keeps `.env`, tests and caches out.
- A new runtime file outside `app/` and `configs/` must be copied in the `Dockerfile`.
- The platform probes `api.healthPath` (`/healthz`).

## 12. Done means

1. `ruff format`, `ruff check`, `mypy`, `pytest` pass.
2. `uvx pip-audit` is clean when a dependency was added.
3. The mandatory final review of the root `AGENT.md` (section 7) is done and its findings fixed.
