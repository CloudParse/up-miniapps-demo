# Deploy to production

A mini-app goes to production from the Up platform, with buttons. Everything the platform needs to know lives in `miniapp.yaml` at the root of this repository. You only open the platform to deploy.

- **Déployer le backend**: builds `api/` into a Docker image, pushes it to your organisation's Gitea registry and asks the platform to deploy that version.
- **Déployer le frontend**: builds `miniapp/` and publishes the mini-app bundle.
- **Déployer le plugin**: builds `plugin/` and publishes the backoffice plugin. It is shown only when `miniapp.yaml` has a `plugin` section.

Each button starts one Gitea Actions workflow of this repository: `.gitea/workflows/deploy-backend.yml`, `deploy-frontend.yml` or `deploy-plugin.yml`. They run on your organisation's own CI runner (label `up-ci`).

**Every part is optional.** A mini-app may have no API, no mini-app bundle or no plugin. When the section is absent from `miniapp.yaml`, the workflow ends successfully with one notice and builds nothing. Keep the workflow files you do not use: never change or delete them (`AGENT.md` section 5.1).

**An invalid `miniapp.yaml` is different.** It fails the run, for every workflow. The file is never read as "nothing to do".

## 1. Configure `miniapp.yaml`

The file [`../miniapp.yaml`](../miniapp.yaml) is already in your project, written with values you can change and with a comment on every line. When your mini-app was created, the platform replaced the identity and display values (`uuid`, `slug`, `name`, `description`, `cardStyle`, `darkTheme`, `deviceTypes`) with the ones of your mini-app, and left the rest as the template wrote it. After that the file is yours: the platform never rewrites it. Delete the sections you do not use. The format: [`../miniapp.schema.json`](../miniapp.schema.json).

A file that still holds the placeholder `uuid` (`00000000-0000-0000-0000-000000000000`) is refused by every workflow: the platform has not filled it yet. It does so at the next Git synchronisation (a few seconds after the mini-app is created).

| Section | Needed for | Fields |
| --- | --- | --- |
| `api` | the backend | `dir` (folder with the `Dockerfile`), `port` (1024 to 65535, the port the container listens on), `healthPath` (answers 200 when healthy), `publicIngress` (public address, default `true`: the mini-app calls its backend through it; `false` keeps the API private), `command` (optional exec-form override) |
| `services` | what the API depends on | `postgres`, `cache`, `bucket` (`true` or `false`). The platform provisions each one and gives the API its settings, with the same names as in your workspace (`DATABASE_URL`, `CACHE_URL`, `CACHE_KEY_PREFIX`, `STORAGE_*`). |
| `miniapp` | the mini-app shown in the shell | `dir`, `build` (shell command), `out` (build output, relative to `dir`) |
| `plugin` | the Studio plugin (optional); the template ships a demo, see `docs/plugin.md` | `dir`, `build`, `out`, `file` (the one ES module, `.js` or `.mjs`, relative to `out`) |

Rules:
- Omit a section to leave that part out. No `api` means no backend, no `miniapp` no bundle, no `plugin` no plugin.
- `uuid` and `slug` never change.
- Never put a secret or an environment variable in the file. Secrets are set in the backoffice.
- Paths are relative to the repository root. They use plain segments only: no leading `/` or `-`, no `.`, `..`, `.git` or `dist-ci` segment, no `//`.
- Only the keys of the schema are allowed. An unknown key, a quoted key or a control character makes the file invalid.
- The file is read by a small strict YAML reader (`.gitea/scripts/miniapp_config.py`). It supports plain and quoted values, `[a, b]` lists and `- a` lists. It refuses anchors, multi-line strings, backslash escapes and tabs.

The sections that fit this template as it is:

```yaml
api:
  dir: api
  port: 8000
  healthPath: /healthz
services:
  postgres: true
  cache: true
  bucket: true
miniapp:
  dir: miniapp
  build: npm ci && npm run build
  out: dist
```

## 2. Deploy

1. Commit and push to the default branch.
2. In the platform, open your mini-app and press **Déployer le backend**, **Déployer le frontend** or **Déployer le plugin**.
3. The platform reads `miniapp.yaml` from the default branch and refuses an invalid file with the line to fix.
4. The platform picks the next version: the last deployed version with the patch number plus one (`1.0.3` becomes `1.0.4`). The changelog is empty.
5. The workflow runs. Follow it from the platform: state, and a link to the Gitea run.

Which commit is built: the workflow checks out `gitea.sha`, the head of the default branch when the run starts. It reads `miniapp.yaml` from that checkout. If you push between your click and the start of the run, the workflow's copy wins: it is the one that decides what is built.

### What the backend workflow does
It has two jobs, `build` then `release`.

Job `build`:
1. Checks that the version is a plain semver (`1.2.3`).
2. Reads `miniapp.yaml`.
3. Builds the image with Kaniko from `<api.dir>/Dockerfile`. There is no Docker daemon. `API_PORT` is set to `api.port`. It pushes `<registry host>/<owner>/<repository>:<version>`.

Job `release` (runs only when `build` built something):
4. Checks the version again, then calls the platform to deploy: `POST .../custom-component/deploy` with `{"tag": "<version>"}`. The platform sets the tag only if the registry holds that version.

Why two jobs: Kaniko unpacks the last stage of your `Dockerfile` over the file system of the runner container. After the build, that container holds the tools of your image (an Alpine image has no `bash`). The runner starts a fresh container for each job, so the call to the platform is a job of its own. Kaniko is the last step of `build`. Do not add a step after it.

Two consequences:
- The steps that run your `Dockerfile` are not given the job token in their environment. `build-image.sh` removes it before Kaniko starts. The platform also refuses the token of the `build` job: it gives a session only to the job `release` (`deploy-frontend` and `deploy-plugin` for the two other workflows) of the default branch. The `release` job does not receive `REGISTRY_TOKEN`.
- This is a limit on what a step is given, not a sandbox. The `RUN` steps of a `Dockerfile` run as root in the container of the runner, so a malicious `RUN` step can read what the runner process holds in memory. The platform limits the damage: the token of a job works only while the job runs and only for this repository, and the session it buys lasts 15 minutes and reaches this one mini-app.
- Each job starts a new runner container. The second job waits for the container to restart, which can take a few minutes when deployments follow each other.

The workflow never changes the component itself and its scripts never delete an image. The platform deletes old images itself: it keeps the image the component runs and the 2 newest.

The `Dockerfile` of this template pins its base images by tag and digest, runs as user `10001`, keeps `/app` read-only for that user, listens on `SERVER_PORT` (`api.port`) and sets `ENVIRONMENT=production`. It has no `HEALTHCHECK`: the platform probes `api.healthPath` through Kubernetes. In production the platform sets `HUB_APP_UUID` (the UUID of the mini-app) and `HUB_CLIENT_SECRET` (a secret it generates once, keeps in Vault and registers on the organization's backend at every deployment) and mounts the Hub's public key. This holds for the component the platform links to the mini-app, that is every project created in Studio. Do not put these two names in Studio yourself: a value you set by hand replaces the platform's, and the secret of the "Regenerate the secret" button of Studio is replaced by the platform's own at the next deployment. The API refuses to start on the development defaults.

### What the frontend workflow does
1. Checks the version and reads `miniapp.yaml` (nothing to do without a `miniapp` section).
2. Builds `miniapp` with its `build` command.
3. Checks `index.base64.gz` in `out` (written by `up-sdk build`: gzip of the base64 of the single-file HTML, the format of the shell and of the web launcher) and copies it as `miniapp-<version>.base64.gz`. The build must run `up-sdk build` (`npm run build` of a mini-app made with `@cloudparse/up-miniapps-sdk`); without that file the job fails with a message saying so.
4. Publishes it with the version and an empty changelog.

### What the plugin workflow does
1. Checks the version and reads `miniapp.yaml` (nothing to do without a `plugin` section).
2. Builds `plugin` with its `build` command.
3. Copies the module `out/<file>` as `plugin-<version>.mjs`.
4. Publishes it as the active plugin version, with an empty changelog.

The packing step refuses a symbolic link, a path that leaves the repository, an output folder that overlaps the sources, a hard link, an `index.base64.gz` that is over 18 MB, that is not one complete gzip stream, or whose content is not the base64 of UTF-8 HTML of at most 64 MB. The plugin module must be a `.js` or `.mjs` file of at most 5 MB (the limit of the organisation API).

## Security model

Read this before you give someone write access to the repository.

**Whoever can push to this repository controls its CI.** The workflows, the scripts in `.gitea/scripts/` and `miniapp.yaml` are all in the repository. A writer can edit a workflow to print or send what the deploy steps receive (the job token, `REGISTRY_TOKEN`) or to read the runner's login file. The mini-app itself has no secret in this repository: its client secret never leaves the organisation's backend. Nothing in this repository prevents that. The checks in the scripts protect you from mistakes and from malformed input. They do not protect you from a writer.

The real limits are on the platform side:
- The job asks for its session with `POST {UP_API_URL}/ci/token`, giving the token Gitea made for that job. The platform asks the organisation's Gitea whether that token belongs to a **running job of the project repository of this mini-app**. A token of a person, of another repository, of another mini-app or of a job that ended gets a 401. The session lasts 15 minutes and works for this mini-app only.
- It allows exactly three calls: publish a mini-app bundle, publish a plugin version, deploy the component with a tag. It has no delete right.
- The platform deploys a tag only if the registry holds it. It keeps the 5 newest bundles and plugin versions, the image the component runs and the 2 newest images.
- The registry account (`REGISTRY_USER`, `REGISTRY_TOKEN`) belongs to this mini-app only. It is a member of one team in the Gitea organisation of this mini-app. That team has the right on packages and on nothing else (no code, no issues).
- With that right the token can push **and delete** the packages of this mini-app's Gitea organisation, and only those. It reaches no other mini-app and no other organisation.
- Each organisation has its own runner, in its own namespace.

What the scripts do on top, as hygiene:
- Build commands run through `run-build.sh` with `env -i`: only `PATH`, a fresh `HOME`, `TMPDIR` and `CI` are set. The runner variables and the secrets are not in their environment. This is **not a boundary**: a writer can change `run-build.sh`.
- Secrets are referenced only by the steps that need them: the registry login by the image build, the job token by the checkout and by the publish and deploy steps.
- Calls use https only (`UP_CI_ALLOW_HTTP=true` allows http on a local development cluster) and never follow a redirect.
- Server error messages are cut to 200 characters and stripped of control characters before they reach the log.

**Limit of the image build.** Kaniko runs the `RUN` steps of your `Dockerfile` as root inside the build, in the runner's container. They can read the registry login file while the build runs. They can also read `REGISTRY_TOKEN` from the environment of the Kaniko process. The login file is removed when the script ends.

## CI contract (set by the platform)

The platform writes these Actions secrets of the repository at every deployment click. Do not edit them. The mini-app has no client id or client secret among them: earlier projects had `UP_CLIENT_ID` and `UP_CLIENT_SECRET`, which the platform now deletes.

| Secret | Content |
| --- | --- |
| `UP_API_URL` | Base of your organisation's API with `/api/v1`, for example `https://api.<organisation>.<domain>/api/v1` |
| `REGISTRY_USER`, `REGISTRY_TOKEN` | Account of this mini-app in the Gitea registry. The scripts only push images. The account can also delete the packages of this mini-app's Gitea organisation. |

The runner of your organisation sets these variables for every job:
- `CI_GITEA_URL`: in-cluster address of Gitea, used to clone.
- `CI_REGISTRY_HOST`: registry host the nodes pull from, and the host of the image. It is required: the workflow fails without it.
- `CI_REGISTRY_INSECURE`: `true` on a local development cluster. It is the only way to build for an insecure registry.
- `CI_ORGANISATION_SLUG`: the organisation.

The runner image is `docker.io/cloudparse/up-ci-runner`. It has Python 3 without PyYAML, Node, `git`, `tar` and `/kaniko/executor`.

The calls the workflows make to the platform:
- `POST /ci/token` with `{"applicationUuid", "repository", "jobToken"}` (the uuid of `miniapp.yaml`, `gitea.repository`, `gitea.token`), answer `{"token", "expiresAt"}`.
- `POST /admin/applications/<uuid>/artifacts` (the mini-app bundle).
- `POST /admin/applications/<uuid>/backoffice-plugin/artifacts` (a plugin version).
- `POST /admin/applications/<uuid>/custom-component/deploy` with `{"tag": "<version>"}`.

Nothing else is called. A test checks it.

## Scripts

All are in `.gitea/scripts/`. The Python ones use the standard library only. Secrets come from the environment, never from arguments.

| File | Role |
| --- | --- |
| `miniapp_config.py` | Reads and validates `miniapp.yaml`: `validate`, `plan --target backend\|frontend\|plugin` (prints `run` or `skip <reason>`), `get <key>` |
| `run-build.sh` | Runs the build command of a section with a scrubbed environment |
| `build-image.sh` | Kaniko build and push (the script never deletes) |
| `bundle.py` | Checks and copies the mini-app `index.base64.gz` and copies the plugin module |
| `up_api.py` | Token, publish a bundle or a plugin version, deploy the component with a tag |
| `ci_http.py` | https-only HTTP helper with no redirects |

Run the tests from the repository root with `.gitea/scripts/check.sh`: Python tests, the Kaniko script test and `shellcheck`. The Python tests need PyYAML and jsonschema. The script installs them with `uv` when they are missing.
