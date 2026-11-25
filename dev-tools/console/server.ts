// The project console (`up-dev` in a Coder workspace, `node dev-tools/console/server.ts` anywhere): one page to start, stop and restart
// the three parts of the project (API, mini-app, plugin), see their state and live logs, and open or preview each of them.
//
// Safety, in short (details in docs/coder.md, section "The project console"):
//   - listens on 127.0.0.1 only; in Coder the app "Console du projet" (share owner) is the only way in, behind the Coder sign-in;
//   - runs the three fixed commands of supervisor.ts, nothing taken from a request: no shell string, no path, no argument;
//   - Host and Origin are checked with the allowlist of the Vite servers (../hostGuard.ts) on every request and WebSocket upgrade;
//   - state-changing requests are POST, need the Origin of the console AND a random token (X-Console-Token) that only the page has;
//   - at most 1 action per 2 s per part and 30 per minute;
//   - the output of the parts is masked (api/.env values, tokens, URL passwords) before it is stored or sent;
//   - serves no file: the only routes are listed in `route`, so there is no path to traverse.
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { appButtonHosts, devAllowedHosts } from "../hostGuard.ts";
import { readMemory, startRefusal } from "./memory.ts";
import { createRateLimiter, hostAllowed, originAllowed, tokenMatches } from "./security.ts";
import { Supervisor, type SupervisorOptions } from "./supervisor.ts";
import { PORTS, type PartId, partUrls } from "./urls.ts";
import { acceptUpgrade, type WsClient } from "./ws.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MAX_WS_CLIENTS = 20;

/** What the page shows about each part. Fixed text. */
const INFO: Record<PartId, { label: string; what: string; folder: string; command: string; open: string; reload: string }> = {
  api: {
    label: "API",
    what: "Le serveur Python (FastAPI) de ta mini-app : les routes /api/v1, la base de données, le cache et le bucket de ton espace DEV.",
    folder: "api/",
    command: "SERVER_HOST=0.0.0.0 uv run --env-file .env python -m app",
    open: "Tester l'API",
    reload: "Se recharge tout seul quand un fichier .py change (uvicorn).",
  },
  miniapp: {
    label: "Mini-app",
    what: "L'application que voit l'utilisateur, dans le simulateur du SDK Up (React, Vite). Elle parle à l'API par /api/.",
    folder: "miniapp/",
    command: "vite --host 0.0.0.0 (npm run dev)",
    open: "Voir la mini-app",
    reload: "Se met à jour toute seule dans le navigateur à chaque fichier modifié (Vite, WebSocket).",
  },
  plugin: {
    label: "Plugin",
    what: "La page d'administration que le Studio Up charge pour ta mini-app, ici sur une page de développement (React, Vite).",
    folder: "plugin/",
    command: "vite --config vite.dev.config.ts (npm run dev)",
    open: "Voir le plugin",
    reload: "Se met à jour toute seule dans le navigateur à chaque fichier modifié (Vite, WebSocket).",
  },
};

export interface ConsoleOptions extends Partial<SupervisorOptions> {
  root: string;
  port?: number;
  host?: string;
  env?: Record<string, string | undefined>;
}

export interface RunningConsole {
  server: http.Server;
  supervisor: Supervisor;
  token: string;
  port: number;
  close(): Promise<void>;
}

/** The hosts the console answers to: loopback names, the Coder button of the console, the port URL of its port, DEV_ALLOWED_HOSTS. */
export function consoleAllowedHosts(port: number, env: Record<string, string | undefined>): string[] {
  return [...devAllowedHosts(port, env), ...appButtonHosts(port, "console", env)];
}

function securityHeaders(res: http.ServerResponse): void {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Cross-Origin-Resource-Policy", "same-origin");
}

function send(res: http.ServerResponse, status: number, body: string, type = "text/plain; charset=utf-8"): void {
  securityHeaders(res);
  res.statusCode = status;
  res.setHeader("Content-Type", type);
  res.end(body);
}

const sendJson = (res: http.ServerResponse, status: number, value: unknown) =>
  send(res, status, JSON.stringify(value), "application/json; charset=utf-8");

export async function startConsole(options: ConsoleOptions): Promise<RunningConsole> {
  const env = options.env ?? process.env;
  const port = options.port ?? PORTS.console;
  const host = options.host ?? "127.0.0.1";
  const token = randomBytes(32).toString("hex");
  const pageTemplate = readFileSync(path.join(HERE, "page.html"), "utf8");
  const supervisor = new Supervisor({ ...options, env, startGuard: options.startGuard ?? (() => startRefusal(readMemory())) });
  const allowed = consoleAllowedHosts(port, env);
  const clients = new Set<WsClient>();
  const perPart = createRateLimiter(1, 2000);
  const overall = createRateLimiter(30, 60_000);

  const urls = () =>
    Object.fromEntries((Object.keys(INFO) as PartId[]).map((id) => [id, partUrls(id, env)])) as Record<PartId, ReturnType<typeof partUrls>>;
  const view = () => {
    const u = urls();
    return supervisor.status().map((s) => ({ ...s, ...INFO[s.id], links: u[s.id] }));
  };
  const broadcast = (message: unknown) => {
    const text = JSON.stringify(message);
    for (const client of clients) client.send(text);
  };
  // the memory figure of the workspace, every 5 s, for the header of the page
  const memoryTimer = setInterval(() => {
    const memory = readMemory();
    if (memory && clients.size > 0) broadcast({ t: "mem", memory });
  }, 5000);
  memoryTimer.unref();
  supervisor.on("state", () => broadcast({ t: "state", services: view() }));
  supervisor.on("log", (id: string, line: string) => broadcast({ t: "log", id, line }));

  const hostOk = (req: http.IncomingMessage) => hostAllowed(req.headers.host, allowed);

  const server = http.createServer((req, res) => {
    if (!hostOk(req)) {
      send(res, 403, "Blocked request: this host is not allowed (DEV_ALLOWED_HOSTS).");
      return;
    }
    const url = new URL(req.url ?? "/", "http://console.invalid");
    const pathname = url.pathname;
    if (req.method === "GET" && pathname === "/healthz") {
      send(res, 200, "ok");
      return;
    }
    if (req.method === "GET" && pathname === "/") {
      const nonce = randomBytes(16).toString("base64");
      const u = urls();
      // the frames the page may open: the origins of the mini-app and of the plugin, nothing else
      const frames = [u.miniapp.open, u.plugin.open].filter((x) => x !== "").map((x) => new URL(x).origin);
      const hostName = req.headers.host as string;
      securityHeaders(res);
      res.setHeader(
        "Content-Security-Policy",
        [
          "default-src 'none'",
          `script-src 'nonce-${nonce}'`,
          `style-src 'nonce-${nonce}'`,
          `connect-src 'self' ws://${hostName} wss://${hostName}`,
          `frame-src ${frames.length > 0 ? frames.join(" ") : "'none'"}`,
          "img-src 'self' data:",
          "base-uri 'none'",
          "form-action 'none'",
          "frame-ancestors 'none'",
        ].join("; "),
      );
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.end(pageTemplate.replaceAll("__NONCE__", nonce).replaceAll("__TOKEN__", token));
      return;
    }
    if (req.method === "GET" && pathname === "/api/state") {
      // no secret in it, but the page of another origin must not read it: same-origin only
      if (req.headers.origin !== undefined && !originAllowed(req.headers.origin, req.headers.host, allowed)) {
        send(res, 403, "origin refused");
        return;
      }
      sendJson(res, 200, { services: view() });
      return;
    }
    const action = /^\/api\/services\/([a-z]+)\/(start|stop|restart)$/.exec(pathname);
    if (action) {
      if (req.method !== "POST") {
        res.setHeader("Allow", "POST");
        send(res, 405, "POST only");
        return;
      }
      if (!originAllowed(req.headers.origin, req.headers.host, allowed)) {
        send(res, 403, "origin refused");
        return;
      }
      if (!tokenMatches(req.headers["x-console-token"] as string | undefined, token)) {
        send(res, 403, "token refused");
        return;
      }
      const id = action[1] as string;
      const verb = action[2] as "start" | "stop" | "restart";
      if (!supervisor.has(id)) {
        send(res, 404, "unknown part");
        return;
      }
      if (!perPart.allow(id) || !overall.allow("all")) {
        res.setHeader("Retry-After", "2");
        send(res, 429, "trop d'actions : attends quelques secondes");
        return;
      }
      req.resume(); // the body (none expected) is ignored
      void supervisor[verb](id).then((result) => sendJson(res, result.ok ? 200 : 409, result));
      return;
    }
    send(res, 404, "not found");
  });

  server.on("upgrade", (req, socket) => {
    const url = new URL(req.url ?? "/", "http://console.invalid");
    // Node drops its own error listener on an upgrade: without this, a client that resets the connection while it is refused (EPIPE)
    // is an uncaught exception that ends the console.
    socket.on("error", () => socket.destroy());
    const refuse = (status: string) => {
      socket.end(`HTTP/1.1 ${status}\r\nConnection: close\r\n\r\n`);
      socket.destroy();
    };
    if (url.pathname !== "/ws") return refuse("404 Not Found");
    if (!hostOk(req)) return refuse("403 Forbidden");
    if (!originAllowed(req.headers.origin, req.headers.host, allowed)) return refuse("403 Forbidden");
    if (!tokenMatches(url.searchParams.get("t"), token)) return refuse("403 Forbidden");
    if (clients.size >= MAX_WS_CLIENTS) return refuse("503 Service Unavailable");
    let client: WsClient | null = null;
    client = acceptUpgrade(req, socket, () => {
      if (client) clients.delete(client);
    });
    if (!client) return;
    clients.add(client);
    // the snapshot: states, then the stored lines of each part
    client.send(JSON.stringify({ t: "state", services: view() }));
    const memory = readMemory();
    if (memory) client.send(JSON.stringify({ t: "mem", memory }));
    for (const id of supervisor.ids()) client.send(JSON.stringify({ t: "logs", id, lines: supervisor.logs(id) }));
  });

  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => resolve());
  });
  const actualPort = (server.address() as { port: number }).port;

  return {
    server,
    supervisor,
    token,
    port: actualPort,
    async close() {
      clearInterval(memoryTimer);
      for (const client of clients) client.close();
      await supervisor.close();
      await new Promise<void>((resolve) => {
        server.close(() => resolve());
        server.closeAllConnections();
      });
    },
  };
}

// `node dev-tools/console/server.ts`: the repository root is two folders up. The process id goes to ~/.config/up/console.pid (up-dev stop).
const isMain = process.argv[1] !== undefined && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const root = path.resolve(HERE, "..", "..");
  const pidFile = process.env.UP_CONSOLE_PID_FILE ?? path.join(os.homedir(), ".config", "up", "console.pid");
  startConsole({ root })
    .then((running) => {
      try {
        mkdirSync(path.dirname(pidFile), { recursive: true });
        writeFileSync(pidFile, `${process.pid}\n`);
      } catch {
        // not fatal: the console runs, but `up-dev stop` needs this file (stop it with Ctrl+C where it runs otherwise)
      }
      console.log(`console du projet : http://localhost:${running.port}/ (127.0.0.1 seulement)`);
      let ending = false;
      const end = () => {
        if (ending) return;
        ending = true;
        console.log("arrêt de la console et de ses parties...");
        void running.close().finally(() => {
          rmSync(pidFile, { force: true });
          process.exit(0);
        });
      };
      process.on("SIGTERM", end);
      process.on("SIGINT", end);
      // last resort: stop the parts (they are detached and would be orphaned) and end
      process.on("uncaughtException", (error) => {
        console.error(`erreur inattendue : ${error.message}`);
        end();
      });
    })
    .catch((error: NodeJS.ErrnoException) => {
      console.error(error.code === "EADDRINUSE" ? `la console tourne déjà (port ${PORTS.console}).` : `la console n'a pas démarré : ${error.message}`);
      process.exit(error.code === "EADDRINUSE" ? 0 : 1);
    });
}
