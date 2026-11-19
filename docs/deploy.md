# Deploy to production

A mini-app goes to production from the Up platform, with two buttons. Everything the platform needs to know lives in `miniapp.yaml` at the root of this repository. You only open the platform to deploy.

- **Déployer le backend**: builds `api/` into a Docker image, pushes it to your organisation's Gitea registry and rolls out your API.
- **Déployer le frontend**: builds `miniapp/` and publishes the mini-app bundle.
- **Déployer le plugin**: builds `plugin/` and publishes the backoffice plugin. Shown only when `miniapp.yaml` has a `plugin` section.

Each button starts one Gitea Actions workflow of this repository (`.gitea/workflows/deploy-backend.yml`, `deploy-frontend.yml`, `deploy-plugin.yml`). They run on your organisation's own CI runner (label `up-ci`).

**Every part is optional.** A mini-app may have no API, no mini-app bundle or no plugin. When the section is absent from `miniapp.yaml`, its workflow ends successfully with a notice, builds nothing and never fails. You can delete the workflow files you do not use.

## 1. Configure `miniapp.yaml`

The platform wrote the file with your mini-app's identity and display settings (`version: 1`). To make the project deployable, set `version: 2` and add the sections you need. A full example with every field: [`miniapp.example.yaml`](miniapp.example.yaml). The format: [`../miniapp.schema.json`](../miniapp.schema.json).

| Section | Needed for | Fields |
| --- | --- | --- |
| `api` | the backend | `dir` (folder with the `Dockerfile`), `port` (the port the container listens on), `healthPath` (answers 200 when healthy), `publicIngress` (public address, default `false`), `command` (optional exec-form override) |
| `services` | what the API depends on | `postgres`, `cache`, `bucket` (`true` or `false`). The platform provisions each one and gives the API its settings, the same names as in your workspace (`DATABASE_URL`, `CACHE_URL`, `CACHE_KEY_PREFIX`, `STORAGE_*`). |
| `miniapp` | the mini-app shown in the shell | `dir`, `build` (shell command), `out` (build output, relative to `dir`) |
| `plugin` | a backoffice plugin (optional) | `dir`, `build`, `out`, `file` (the one ES module, `.js` or `.mjs`, relative to `out`) |

Rules:
- Omit a section to leave that part out. No `api` means no backend, no `miniapp` no bundle, no `plugin` no plugin.
- `uuid` and `slug` never change. Never put a secret or an environment variable in the file: secrets are set in the backoffice.
- Paths are relative to the repository root, never absolute, never `..`.
- The build commands run on the CI runner with no secret in their environment.

The sections that fit this template as it is:

```yaml
api:
  dir: api
  port: 8000
  healthPath: /healthz
services: {postgres: true, cache: true, bucket: true}
miniapp: {dir: miniapp, build: npm ci && npm run build, out: dist}
```

## 2. Deploy

1. Commit and push to the default branch.
2. In the platform, open your mini-app and press **Déployer le backend** and/or **Déployer le frontend**.
3. The platform reads `miniapp.yaml` from the default branch. An invalid file is refused with the line to fix and nothing changes. The workflow reads it again: an invalid file fails the run, an absent section ends it successfully.
4. The platform picks the next version: the last deployed version with the patch number plus one (`1.0.3` becomes `1.0.4`). The changelog is empty.
5. The workflow runs. Follow it from the platform (state and link to the Gitea run).

### What the backend workflow does
1. Validates `miniapp.yaml`.
2. Builds the image with Kaniko from `<api.dir>/Dockerfile` (no Docker daemon), with `API_PORT` set to `api.port`, and pushes `<gitea host>/<owner>/<repository>:<version>`.
3. Calls the platform to roll out the component. The platform set the new image tag before it started the workflow.
4. Deletes every other image of the repository: only the latest image is kept.

The `Dockerfile` of this template runs as user `10001`, listens on `SERVER_PORT` (`api.port`) and sets `ENVIRONMENT=production`. In production the platform sets `HUB_APP_UUID` and `HUB_CLIENT_SECRET` and mounts the Hub's public key. The API refuses to start on the development defaults.

### What the frontend workflow does
1. Reads `miniapp.yaml` (nothing to do without a `miniapp` section).
2. Builds `miniapp` with its `build` command.
3. Packs `miniapp-<version>.tar.gz`, the content of `out`.
4. Publishes it with the version and an empty changelog.
5. Calls the organisation API's `prune-old`: the 5 newest bundles are kept (the API's minimum).

### What the plugin workflow does
1. Reads `miniapp.yaml` (nothing to do without a `plugin` section).
2. Builds `plugin` with its `build` command.
3. Copies the module `out/<file>` as `plugin-<version>.mjs` and publishes it as the active plugin version, with an empty changelog.
4. Deletes the plugin versions beyond the 5 newest.

## CI contract (set by the platform)

The platform writes these Actions secrets of the repository when it creates the project. Do not edit them.

| Secret | Content |
| --- | --- |
| `UP_API_URL` | Base of your organisation's API with `/api/v1`, e.g. `https://api.<organisation>.<domain>/api/v1` |
| `UP_CLIENT_ID` | Client id of this mini-app |
| `UP_CLIENT_SECRET` | Client secret of this mini-app |
| `REGISTRY_USER`, `REGISTRY_TOKEN` | Account of the Gitea registry that pushes and prunes images (`write:package`) |

The scripts call the organisation API with a token obtained from `POST {UP_API_URL}/ci/token` (`{"clientId", "clientSecret"}`, answer `{"token", "expiresAt"}`). That token only works for this mini-app. The calls are `POST /admin/applications/<uuid>/artifacts`, `DELETE /admin/applications/artifacts/prune-old?keep=5`, `POST .../backoffice-plugin/artifacts` with `GET` and `DELETE` of that collection, and `POST /admin/applications/<uuid>/custom-component/deploy`.

## Scripts

All in `.gitea/scripts/`, standard library only (the runner has Python 3 and no PyYAML), secrets only from the environment:

| File | Role |
| --- | --- |
| `miniapp_config.py` | Reads and validates `miniapp.yaml` (`validate`, `plan --target backend\|frontend\|plugin` prints `run` or `skip <reason>`, `get <key>`) |
| `build-image.sh` | Kaniko build and push |
| `bundle.py` | Packs the mini-app `.tar.gz` and copies the plugin module |
| `up_api.py` | Token, publish, prune (`prune-old` for the mini-app, one by one for the plugin), roll out the component |
| `registry_prune.py` | Keeps only the current image in the Gitea registry |

Run the tests from the repository root with `.gitea/scripts/check.sh` (Python tests, the shell test and `shellcheck`).
