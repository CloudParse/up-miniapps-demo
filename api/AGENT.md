# api/AGENT.md: mini-app backend (`up-miniapps-demo-api`)

Read the root `AGENT.md` first (architecture, security rules, mandatory final review). This file covers the Python / FastAPI backend only.

Paths in this file are relative to the repository root. The absolute paths of this workspace are in `CLAUDE.local.md`, written by `up-project-setup` (git-ignored).

## Stack and commands

Python 3.14, FastAPI, Pydantic v2, PyJWT, managed with **uv** (never `pip`, `poetry` or `requirements.txt`). Quality tools: ruff (lint + format), mypy `--strict`, pytest.

```bash
uv sync                                          # install from uv.lock
uv run python -m app                             # dev server with reload, http://localhost:21514/docs (`python -m app` in the venv works too)
uv run ruff format . && uv run ruff check .
uv run mypy app tests
uv run pytest
```

## Architecture

```text
api/
├── app/
│   ├── main.py            create_app(): builds and wires the application (a factory, no global app)
│   ├── __main__.py        dev entry point (uvicorn): loads api/.env, then starts the server
│   ├── api/
│   │   ├── router.py      mounts the routers under /api/v1
│   │   ├── deps.py        FastAPI dependencies: how routes obtain services and the current user
│   │   └── routes/        one module per resource: parse input, call a service, return a schema
│   ├── core/
│   │   ├── config.py      typed config: TOML file + environment overrides
│   │   ├── dotenv.py      loads api/.env for the dev entry point (never overrides the environment)
│   │   ├── security.py    verification of the Hub's user tokens
│   │   └── errors.py      AppError hierarchy and handlers
│   ├── schemas/           Pydantic models: the API contract (request and response bodies)
│   └── services/          business logic, plain Python, knows nothing about HTTP (resource_service: are the DEV resources up)
├── configs/config.toml    defaults; every key overridable by environment
├── tests/
└── pyproject.toml
```

The default architecture is MVC with a service layer. The skill `up-miniapp-api` details it.
- Model: `models/` and `repositories/`, created with the first table.
- View: `schemas/`, the JSON contract.
- Controller: `api/routes/`.
- Services: `services/`, the business rules.

Dependencies point one way: `routes -> services -> (repositories, schemas, core)`. A service never imports from `api/`; a route never contains business rules.

Add layers **when a use case needs them**, not before:

- `models/` (ORM entities) and `repositories/` (database access, one class per aggregate, returning domain objects, never leaking the ORM session upward) appear with the first table. Services depend on a repository, routes never touch it.
- `services/hub_client.py` appears with the first call to the Hub (see "Calling the Hub").

### Adding an endpoint

1. `schemas/<resource>.py`: request/response models inheriting `CamelModel`.
2. `services/<resource>_service.py`: the logic, as small typed methods. Raise `AppError` subclasses for expected failures.
3. `api/deps.py`: a `get_<resource>_service` provider and an `Annotated` alias.
4. `api/routes/<resource>.py`: a thin function, typed return, `summary`, constrained inputs.
5. Mount the router in `api/router.py`.
6. `tests/test_<resource>.py`: success, validation failure, auth failure (and the 403 for an admin route).

`hello` (public), `me` (authenticated) and `admin/hello` (admin only) are the worked examples; pick the access level first, see "Public, authenticated and admin routes".

`ws` (`api/routes/realtime.py`, WebSocket) is the worked example of a push: the hub in `services/realtime_service.py` broadcasts, the mini-app listens. It is public, so push only what every member may see. See `docs/realtime.md`.

## FastAPI practices

- **Routers and prefix**: one `APIRouter` per resource, mounted once in `api/router.py` under `/api/v1`. `GET /healthz` stays unversioned and public.
- **Schemas**: every body in and out is a Pydantic model. Return the model (or a typed return annotation), never a bare `dict` for domain data. Wire keys are camelCase through `CamelModel`; Python stays snake_case.
- **Validation**: express constraints in the type (`Query(min_length=1, max_length=40, pattern=...)`, `Field(...)`). Reject, do not sanitise silently. Validation failures are automatic 422s.
- **Dependencies**: collaborators (services, current user, verifier) come from `Depends`, defined in `api/deps.py`. Tests swap them through `app.dependency_overrides` or by building the app with a test config.
- **Errors**: raise `AppError` subclasses (`UnauthorizedError`, ...) from services and dependencies; the handler renders `{"error": {"code", "message"}}`. Add a subclass per new failure class instead of raising `HTTPException` ad hoc. Unexpected exceptions become a generic 500; the traceback is logged, never returned.
- **Configuration**: read once through `get_config()`, injected into `create_app(config)`. Nothing else reads `os.environ`.
- **OpenAPI**: every route has a `summary` and typed models so `/docs` is the live documentation. Docs and `openapi.json` are disabled when `environment = "production"`.
- **Tests**: `TestClient` against `create_app(test_config)`. Prefer the real app over mocks; fake only what is external (the Hub). Sign test tokens with a locally generated key pair (see `tests/conftest.py`).

## Python practices

- Type every function signature and variable that is not obvious; `mypy --strict` must pass. Use `X | None`, built-in generics (`list[str]`), `Annotated`.
- Explicit names; functions short (one level of abstraction, ideally under ~20 lines); early returns over nesting.
- A class only when it holds state or a contract (a service with collaborators, a verifier). Otherwise a function. No class used as a namespace.
- `dataclass(frozen=True)` or Pydantic models for data; no loose dicts crossing function boundaries.
- Catch the narrowest exception, add context, re-raise with `from`; never `except Exception: pass`. Log with `logger = logging.getLogger(__name__)` and key/value `extra`, never `print`, never a secret or token.
- No mutable defaults, no module-level side effects (no global app, no connection at import time).
- ruff enforces style, imports and common bugs; do not silence a rule without a one-line reason.

## Public, authenticated and admin routes

Decide the access level of **every** route when you create it. There are three, and the default for anything touching user data is "authenticated", never "public".

| Level | Who may call | How it is enforced | Example |
| --- | --- | --- | --- |
| Public | Anyone, no token | No dependency. Use only for data that is safe for the whole internet. | `GET /api/v1/hello`, `GET /healthz` |
| Authenticated | Any user holding a valid scoped token for **your** app | `CurrentUserDep` (`get_current_user`) | `GET /api/v1/me` |
| Admin | Only administrators | `require_admin`, declared once on an `/admin` router | `GET /api/v1/admin/hello` |

### How admin is decided: the scope in the token

The backend never keeps its own list of admins. The Hub decides, and says so inside the signed token:

1. The shell asks the Hub for a scoped token: `POST /applications/{uuid}/token`. A mini-app never asks for scopes. The Hub ignores a `scopes` field in the body.
2. The Hub puts `["profile:miniapp:admin"]` in the token's `scp` claim **only if that user has the global Hub flag `miniapp_admin`**. The flag is not a per-app grant: it is valid for every mini-app. For anyone else the token has no `scp` claim (or an empty one).
3. A token made in the Studio (`POST /admin/applications/{uuid}/token`, tab "Scope tokens", by an organisation admin, a super user, or a mini-app administrator of this app) always carries `profile:miniapp:admin`.
4. `core/security.py` sets `AuthenticatedUser.is_admin` (the scope is in `scp`). `require_admin` turns a non-admin into `403 forbidden`.

Because the token is signed by the Hub and verified here, a client cannot add the scope to its own token.

```python
# api/deps.py
def require_admin(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if not user.is_admin:
        raise ForbiddenError("Administrator access required.")
    return user


# api/routes/admin.py: the guard sits on the router, so no admin route can forget it
router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


@router.get("/hello")
def say_hello_to_admin(service: HelloServiceDep) -> Greeting: ...
```

Rules:

- Every admin-only route lives under `/api/v1/admin/`, in `api/routes/admin.py` (or one admin module per resource, mounted with the same guard). Never mix admin and user routes in one router.
- Status codes: `401` = no or invalid token (who are you?), `403` = valid token without the right (you may not).
- Admin power is checked from the token on every request; never cache "is admin" or trust a flag sent by the client (body, header, query).
- Admin routes never return more than needed, and are covered by three tests: admin `200`, regular user `403`, anonymous `401` (`tests/test_admin.py`).

### Trying it

The tests cover the three access levels without a Hub (`tests/test_admin.py`, `tests/test_me.py`): `tests/conftest.py` signs tokens with a locally generated key pair standing in for the Hub's. Against the real DEV backend, sign in as a test user in the simulator (`miniapp/`): every call then carries a real token. By hand:

```bash
curl -s localhost:21514/api/v1/hello                                  # 200, public
curl -s -o /dev/null -w '%{http_code}\n' localhost:21514/api/v1/me    # 401 without a token
```

The admin scope needs no setting on the application: the Hub adds it on its own for a user with the global Hub flag `miniapp_admin`.

## Configuration (`configs/config.toml`)

Same convention as every Go backend of the Up family:

- Keys are `snake_case`, sections are TOML tables (`[server]`, `[hub]`, `[database]`, `[cache]`, `[storage]`, `[cors]`).
- `[database] url`, `[cache] url` and `key_prefix`, `[storage] endpoint`, `access_key`, `secret_key`, `bucket` are your mini-app's own DEV resources: the workspace writes them to `api/.env` as `DATABASE_URL`, `CACHE_URL`, `CACHE_KEY_PREFIX`, `STORAGE_*` (`../docs/coder.md`). Every cache key and channel must start with `cache.key_prefix`.
- **`environment` is top-level**, never nested, so it binds to a plain `ENVIRONMENT` variable (Kubernetes injects exactly that).
- **Environment override**: the dotted key, upper-cased, dots replaced by underscores. `hub.base_url` becomes `HUB_BASE_URL`, `server.port` becomes `SERVER_PORT`. Lists are comma-separated. Only keys present in the TOML can be overridden, so the file lists every setting.
- The committed file holds safe defaults and **empty placeholders for secrets**. The one exception: `hub.app_uuid` and `hub.client_secret` default to the DEV backend's shared mock registration (`0d0d0d0d-0000-4000-8000-000000000001`, `mock_secret`), which opens nothing outside the DEV backend. Real values come from the environment (`api/.env`, gitignored, read by `python -m app` itself). Secrets are `SecretStr`.
- To add a setting: add the key to `config.toml`, the field to the matching model in `core/config.py`, a test in `tests/test_config.py`.

## Production image (`Dockerfile`)

The CI builds `Dockerfile` with Kaniko (`docs/deploy.md`). Keep it: multi-stage, dependencies from `uv.lock` (`uv sync --frozen --no-dev`), a non-root user (`10001`), no secret, pinned base images, `ENVIRONMENT=production`, `SERVER_HOST=0.0.0.0` and `SERVER_PORT` from the build argument `API_PORT` (`miniapp.yaml` `api.port`). A new runtime file (outside `app/` and `configs/`) must be copied in the Dockerfile. `.dockerignore` keeps `.env`, tests and caches out of the image. Probe `GET /healthz` (`api.healthPath`).

## Registering a mini-app on the CloudParse backend

### The two backends

- **CloudParse backend (the "Hub")**: the official Up backend (`cloudparse/up-backend`). It owns users, sign-in, the catalogue of mini-apps, push, points and achievements. It signs the tokens users carry. It is the authority. In a Coder workspace your backend uses the organisation's DEV backend, `http://backend-service:8080/api/v1` (`hub.base_url`).
- **Your mini-app backend** (this project): owns **your** data and rules. It never sees passwords or phone numbers; it only receives a token saying *which user* is calling, *from which mini-app*.

### How your backend is identified

Registration creates an **Application** on the Hub. The Hub returns two things:

| Value | Meaning | Sensitivity |
| --- | --- | --- |
| `uuid` | Public identity of the mini-app. Becomes the `aud` (audience) of every user token minted for it. | Public |
| `clientSecret` | Password of your backend towards the Hub. **Shown once.** | **Secret** |

It also stores the metadata the shell needs: `name`, `httpBackendUrl` (where the frontend should call your backend), optional `wsBackendUrl`, `allowedOrigins`, `isDarkTheme`, `cardStyle`, `deviceTypes`. The shell receives `httpBackendUrl` at launch, which is how the frontend finds your backend without hardcoding it.

### How it registers

An admin calls `POST /api/v1/admin/applications` on the Hub (in production, from the Up back office):

```json
{
  "name": "My Mini-App",
  "description": "What it does",
  "httpBackendUrl": "https://api.my-miniapp.example/api/v1",
  "allowedOrigins": ["https://api.my-miniapp.example"],
  "isDarkTheme": true,
  "cardStyle": "navy"
}
```

Response (`201`): `{ "application": { "uuid": "...", ... }, "clientSecret": "..." }`. `name` must be unique (min 3 characters). `cardStyle` is required: the gradient of the mini-app's card on the shell home screen, one of `navy`, `blush`, `night`, `mist`, `violet`. A lost secret cannot be read back: an admin calls `POST /api/v1/admin/applications/{uuid}/regenerate-secret`, and you update your environment.

### Getting the credentials

In development every mini-app uses the DEV backend's shared mock registration: the defaults of `config.toml`, nothing to do. The DEV backend's public key is written by the workspace (`HUB_PUBLIC_KEY_PATH` in `api/.env`). In production the platform sets `HUB_APP_UUID`, `HUB_CLIENT_SECRET` and the key of the real registration.

### Credentials and secrets

- `HUB_CLIENT_SECRET` lives only in the environment of the deployed backend (a secret store in production, `api/.env` locally). Never in `config.toml`, git, logs, the frontend or an image.
- `app_uuid` is not secret, but keep it in the same place so the two always match.
- Rotate with `regenerate-secret` if it ever leaks.

### How requests are authenticated (user → your backend)

1. A user opens your mini-app. The shell asks the Hub for a **scoped token** for `(user, your app uuid)`: ES256 JWT, short-lived, `sub` = user UUID, `aud` = your app uuid, `scp` = `["profile:miniapp:admin"]` for a user with the global Hub flag `miniapp_admin`, absent otherwise. The mini-app gets the whole user profile from the shell: there are no profile scopes and no per-scope consent.
2. The shell attaches it as `Authorization: Bearer <token>` to every request the mini-app sends (through the SDK).
3. `core/security.py` verifies it **offline** with the Hub's public key (`hub.public_key_path`): signature, algorithm pinned to ES256, `exp`, and `aud` equal to your app uuid. That audience check stops a token minted for another mini-app from working on yours.

Your backend therefore only needs the Hub's **public** key and can never forge a token. In `development`, the audience of the shell's "Vite Dev" entry (`99999999-9999-9999-9999-999999999999`) is also accepted.

### Calling the Hub (your backend → Hub, machine to machine)

Only needed when you use Hub features (award points, push, achievements...). Authenticate as the app, not as a user:

```text
POST {hub.base_url}/partner/auth/login   {"appUuid": "...", "clientSecret": "..."}
→ {"token": "<M2M JWT>", "expiresAt": 86400}
```

Send the token as `Authorization: Bearer` on `/partner/...` routes. Cache it and refresh it a few minutes before expiry. Put this in `services/hub_client.py` behind a small class with an injectable `httpx2` client (so tests can stub the Hub), with a timeout on every call. Some partner capabilities (push, phone lookup, ...) must additionally be allow-listed for your app uuid in the Hub's configuration. Ask the Up team; do not look for a way around it.

### Checking the registration

The machine login proves the credentials work (run in `api/`, after `set -a; . ./.env; set +a`):

```bash
jq -n '{appUuid: env.HUB_APP_UUID, clientSecret: env.HUB_CLIENT_SECRET}' \
  | curl -fsS -X POST http://backend-service:8080/api/v1/partner/auth/login -H 'Content-Type: application/json' --data @- \
  | jq -e .token >/dev/null && echo "credentials OK"
```

Automated tests never need the Hub: `tests/conftest.py` signs tokens with a locally generated key pair standing in for the Hub's.

## Definition of done

`ruff format`, `ruff check`, `mypy` and `pytest` pass, then the **mandatory final review** of the root `AGENT.md` (section 7) is done, with the backend points in mind: thin routes, logic in services, validated inputs, authenticated routes protected, no secret anywhere, no information leak in errors.
