---
name: up-platform-guide
description: Answers questions about Up and this project. What Up is. Roles and permissions (Classic, Dev, Admin mini-app, Admin) and what to do when lost. How to run the project in development (Coder workspace, port forwarding, test users). How to go to production (miniapp.yaml, tab "Déploiement" in the Studio of up.cloudparse.fr). How to show the mini-app on the web (deviceTypes). Use for any "what is", "how do I", "where is" or "why does it not work" question.
---

# Up: guide for mini-app developers

How to use this skill:
- Answer in the user's language (French or English).
- Give the short answer first, then the file that holds the detail.
- Never guess a value. When this skill and the repository disagree, the repository wins: `AGENT.md`, `SETUP.md`, `docs/coder.md`, `docs/deploy.md`.

## 1. What Up is

- **Up** is a mobile super-app made by CloudParse. One phone app hosts many small apps.
- **The shell** is the Up phone app, on iOS and Android. It loads each mini-app in a WebView.
- **A mini-app** is a web page. Here it is React, built into one `dist/index.html`.
- **The SDK** `@cloudparse/up-miniapps-sdk` is the only way a mini-app talks to the phone and to Up.
- **The Hub** is the Up backend of the organisation. It owns users, sign-in, the mini-app catalogue, push, points and achievements. It signs the user tokens.
- **The mini-app API** is `api/` here. It owns the mini-app's own data. It checks the Hub's tokens with the Hub's public key.
- **The platform** is the website `https://up.cloudparse.fr`.
- **The Studio** is the management area of an organisation. Open it from the top bar entry "Studio". Its pages are under `/o/<organisation>`. Some docs call it the backoffice.
- **An organisation** has its own Hub, Gitea (code), Coder (workspaces), DEV environment and production.

## 2. Roles, rights and permissions

Your role is the badge on the profile button, top right of `https://up.cloudparse.fr`.

Key rule: a member of a mini-app is an administrator of that mini-app. Being added to a mini-app also makes you a developer of the organisation (checked 2026-11-20).

### Classic

- Who: a member of the organisation, with no mini-app and no developer right.
- Can: use the mini-apps in the Up app.
- Can: open "Accueil" and "Apps" on the website. "Apps" lists the mini-apps with `WEB`.
- Cannot: open the Studio.
- Cannot: use Coder or Gitea.

### Dev

- Who: a member with the developer right.
- Can: everything a Classic member can.
- Can: open the Studio. Its home shows "Environnement de développement", with the link to Coder.
- Can: use Coder, Gitea and Grafana. Grafana data is read-only.
- Cannot: manage users.
- Cannot: deploy.
- A Dev who is in no mini-app has Coder, but no project workspace.

### Member of a mini-app (mini-app administrator)

- Who: a member added to a mini-app by an admin of the organisation. This also makes them Dev.
- Gets: one Coder workspace for that mini-app, and access to its Gitea repository.
- Can: open "Mes mini-apps" in the Studio. Each of their mini-apps has the tabs "Réglages", "API", "Plugin", "Artefacts", "Scope tokens" and "Git".
- Cannot: deploy. The tabs "Déploiement", "Administrateurs" and "Statistiques" are hidden.
- Cannot: manage other mini-apps or users.
- Badge: "Dev" in most cases. "Admin mini-app" shows on a session opened from the Up app, or before the developer right is active.

### Admin

- Who: the admin account of the organisation, `<organisation>-admins`. It is a separate account.
- Can: every Studio page. "Utilisateurs", "Mini-apps", "Plugins", "Artefacts", "Scope tokens", "Bannières", "Chat", "Succès", "Statistiques", "Ressources et limites", "Composants", "Paramètres".
- Can: create mini-apps, add their members, give or remove the developer right.
- Can: deploy. Only this role deploys.
- Cannot: open a web mini-app. It is an admin account, not a member account.

### Who gives which right

| Right | Given by | Where in the Studio |
| --- | --- | --- |
| Dev | An admin of the organisation | "Utilisateurs", the member's page, switch "Rôle développeur" |
| Member of a mini-app | An admin of the organisation | "Mini-apps", the mini-app, tab "Administrateurs" |
| Admin | CloudParse | CloudParse creates the admin account |

- Adding someone to a mini-app also gives them the developer right.
- Removing someone from their last mini-app takes the developer right away.
- Turning off "Rôle développeur" asks "Retirer le droit développeur ?".
- A new developer gets Coder, Gitea and Grafana at their first sign-in on the website.

### If you are lost

| Problem | What to do |
| --- | --- |
| No "Studio" in the top bar | You are Classic. Ask an admin of the organisation to add you to the mini-app. |
| The Studio shows only "Accueil" | You are Dev, but in no mini-app. Ask an admin of the organisation to add you to the mini-app. |
| No workspace for your mini-app in Coder | First, link Gitea in Coder: open `/external-auth/gitea` on your Coder (2026-11-19). The workspace then appears. Still nothing? Ask an admin of the organisation to check you are in the mini-app. |
| No tab "Déploiement" | Normal. Only an admin of the organisation deploys. Push your code, then ask them. |
| The Admin account cannot open a web mini-app | Normal. Use your member account. |
| You signed in from the Up app as mini-app administrator, and web mini-apps do not open | Normal for that session. Sign in on the website with your member account. |
| A right was just given and nothing changed | Sign out of the website. Sign in again. |

## 3. Development (Coder workspace)

The platform creates, once:
- a Gitea repository `<organisation>-<mini-app>-<4 characters>`. It is a copy of this demo, shared by the mini-app's members;
- a Coder workspace named after the mini-app, at `https://coder.<organisation>.<domain>`.

At each start, the workspace:
1. clones the repository (the first time);
2. writes `api/.env`: DEV database, cache, bucket and Hub public key;
3. installs the dependencies;
4. installs the SDK's Claude Code plugin.

A step failed? Run `up-project-setup` in a terminal.

Start the project:

```bash
cd ~/<repository>/api && uv run --env-file .env python -m app   # terminal 1, 127.0.0.1:21514
cd ~/<repository>/miniapp && npm run dev                         # terminal 2, port 21515
```

See the mini-app:
1. In the Coder dashboard, open the workspace app **Mini-app** (port 21515). Only you can open it.
2. No "Mini-app" app? Forward the port to your laptop. Then open `http://localhost:21515`.

   ```bash
   coder port-forward <workspace> --tcp 21515:21515
   ```

3. The SDK simulator shows a phone frame. It asks for a test user. Pick one of the 15 DEV users.
4. To change user, open the tab "Compte".

Limits in development (2026-11-19, `docs/coder.md`):
- The page runs in the browser simulator. The Up phone app does not load a workspace build.
- The platform blocks port sharing. A colleague opens the app in their own workspace.
- Only port 21515 is needed. Vite sends `/api/` to the API and `/hub/` to the DEV Hub.

## 4. Production (Studio of up.cloudparse.fr)

Who does what (checked 2026-11-20):
- The developer writes `miniapp.yaml` and pushes.
- An admin of the organisation presses the deploy buttons.

Steps:
1. Open `miniapp.yaml` at the repository root. The platform wrote it.
2. Set `version: 2`.
3. Add the sections you need. Copy them from `docs/miniapp.example.yaml`.
   - `api`: `dir`, `port`. Optional: `healthPath`, `publicIngress`, `command`.
   - `services`: `postgres`, `cache`, `bucket`.
   - `miniapp`: `dir`, `build`, `out`.
   - `plugin`: `dir`, `build`, `out`, `file`.

   Every section is optional. Leave out the parts the mini-app does not have.
4. Commit and push to the default branch.
5. The admin opens **Studio**, then **Mini-apps**, then the mini-app, then the tab **Déploiement**.
6. The admin presses **Déployer le backend**, **Déployer le frontend** or **Déployer le plugin**.
7. The platform picks the version: the last one, patch + 1 (`1.0.3` becomes `1.0.4`).
8. The platform starts the Gitea workflow. The Studio shows the run's state and a link to it.

What each button does:
- **Déployer le backend**: builds `api/Dockerfile`, pushes the image to the Gitea registry, deploys that version.
- **Déployer le frontend**: builds `miniapp/`, publishes `miniapp-<version>.tar.gz` for the Up app.
- **Déployer le plugin**: publishes one ES module for the organisation's backoffice. The button shows only when `miniapp.yaml` has a `plugin` section.

Rules:
- A backend or frontend run without its section builds nothing. It ends green.
- An invalid `miniapp.yaml` fails the run. The error gives the line to fix.
- Never put a secret in `miniapp.yaml`.
- Full detail: `docs/deploy.md`.

## 5. Devices and the web (`deviceTypes`)

`deviceTypes` lists where the mini-app is shown. `miniapp.schema.json` describes it.

| Value | Studio chip | Where |
| --- | --- | --- |
| `PHONE` | "Téléphone" | The Up app on a phone, iOS and Android |
| `TABLET` | "Tablette" | The Up app on a tablet |
| `DESKTOP` | "Ordinateur" | The Up app on a computer |
| `TV` | "TV" | The Up app on a TV |
| `WEB` | "Web" | The page "Apps" of the Up website |

- There is no iOS-only or Android-only value.
- Values combine, for example `deviceTypes: [PHONE, WEB]`.
- A mini-app created in the Studio starts with `PHONE` only.

Turn on the web:
1. Check that the mini-app works in a desktop browser. A feature that needs the phone (camera, location, haptics) needs a fallback.
2. Add `WEB` to `deviceTypes` in `miniapp.yaml`. Commit and push.
3. Open the mini-app in the Studio, tab **Réglages**.
   - An admin of the organisation: **Mini-apps**, then the mini-app.
   - A member of the mini-app: **Mes mini-apps**, then the mini-app.
4. Press the chip **Web** under "Appareils cibles". Save.
5. No frontend version published yet? An admin of the organisation presses **Déployer le frontend**.
6. The mini-app appears on the page "Apps" of `https://up.cloudparse.fr`.

The Studio value is the one the platform uses. The display settings of `miniapp.yaml` are not applied by CI yet (2026-11-20). Keep both equal.

## 6. Common questions

| Question | Answer |
| --- | --- |
| No "Mini-app" app in Coder | Run `coder port-forward <workspace> --tcp 21515:21515` on your laptop. |
| Vite says "Blocked request. This host is not allowed" | Add the host to the shell variable `DEV_ALLOWED_HOSTS` (comma separated). Restart `npm run dev`. |
| API calls fail with 401 | The token is missing, expired or for another mini-app. A call without the SDK client (curl, a hand-written `fetch`) has no token: use `services/`. An expired token: pick the test user again in the tab "Compte". |
| API calls fail with 503 "Authentication is not configured" | `api/.env` has no Hub key. Run `up-project-setup`. Restart the API. |
| `GET /api/v1/resources` shows a resource down | Restart the workspace. Still down? Ask an admin of the organisation. |
| Where are the secrets in production? | The platform sets them: `HUB_APP_UUID`, `HUB_CLIENT_SECRET`, the Hub key, the service settings. Never in git. |
| No tab "Déploiement" | Only an admin of the organisation deploys (section 2). |
| The run fails at "build" | Open the Gitea run from the Studio. Run the same build in the workspace. |
| The app is not on the website | Follow section 5. |
| An SDK method name | Read the SDK README or its `.d.ts`, or the `up-miniapp-builder` skill of the SDK plugin. Never guess. |

## 7. Where to go next

- Mini-app code: skill `up-miniapp-frontend`, then `miniapp/AGENT.md`.
- API code: skill `up-miniapp-api`, then `api/AGENT.md`.
- Project workflow and checks: skill `up-miniapp-project`, then `AGENT.md`.
- Support: `support@cloudparse.fr`.
