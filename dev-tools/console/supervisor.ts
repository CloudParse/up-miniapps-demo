// The supervisor of the console: starts, stops and restarts the THREE fixed parts of the project, each in its own process group,
// probes their ports, keeps the last lines of their output (secrets masked) and tells the listeners what changes.
//
// What it runs is fixed here, never taken from a request: the same commands as `up-api`, `up-miniapp` and `up-plugin` of the
// workspace (and dev-tools/up-dev.sh), except that Vite is started directly (`node_modules/.bin/vite` is what `npm run dev` runs;
// the npm wrapper alone costs about 160 MB of the 2 GiB of a workspace).
import { type ChildProcess, spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { createMasker, parseEnvFile, secretValues } from "./mask.ts";
import { PORTS, type PartId } from "./urls.ts";

export type State = "stopped" | "starting" | "running" | "crashed" | "external" | "blocked";

export interface ServiceDef {
  id: PartId;
  /** folder of the repository root */
  dir: string;
  port: number;
  /** executable, relative to `dir` when it has a slash (checked to exist), else looked up in PATH */
  command: string;
  args: string[];
  /** variables added to the filtered environment */
  env: Record<string, string>;
  /** a file or folder that must exist (dependencies, settings), with the message when it does not */
  needs: { path: string; message: string }[];
}

/** The three fixed parts. Memory: NODE_OPTIONS caps the heap of a Vite server, see docs/coder.md ("Memory"). */
export function defaultServices(): ServiceDef[] {
  return [
    {
      id: "api",
      dir: "api",
      port: PORTS.api,
      command: "uv",
      args: ["run", "--env-file", ".env", "python", "-m", "app"],
      env: { SERVER_HOST: "0.0.0.0" },
      needs: [{ path: ".env", message: "api/.env est absent : lance up-project-setup (il l'écrit depuis Vault)." }],
    },
    {
      id: "miniapp",
      dir: "miniapp",
      port: PORTS.miniapp,
      command: "node_modules/.bin/vite",
      args: ["--host", "0.0.0.0"],
      env: { CI: "true", NODE_OPTIONS: "--max-old-space-size=384" },
      needs: [{ path: "node_modules/.bin/vite", message: "dépendances absentes dans miniapp/ : lance up-project-setup." }],
    },
    {
      id: "plugin",
      dir: "plugin",
      port: PORTS.plugin,
      command: "node_modules/.bin/vite",
      args: ["--config", "vite.dev.config.ts"],
      env: { CI: "true", NODE_OPTIONS: "--max-old-space-size=320" },
      needs: [{ path: "node_modules/.bin/vite", message: "dépendances absentes dans plugin/ : lance up-project-setup." }],
    },
  ];
}

// The environment a part gets: what a dev server needs, NOT the secrets of the workspace agent (UP_OIDC_TOKEN, the Coder token...).
// The API reads its settings from api/.env itself.
const ENV_ALLOW = /^(PATH|HOME|USER|LOGNAME|LANG|LC_[A-Z]+|TZ|TMPDIR|TERM|SHELL|HOSTNAME|GOPATH|VSCODE_PROXY_URI|CODER_WORKSPACE_AGENT_NAME|DEV_[A-Z_]+|UV_[A-Z_]+|NPM_CONFIG_[A-Z_]+|NODE_[A-Z_]+|PYTHON[A-Z_]*|XDG_[A-Z_]+)$/;

/** The filtered environment of a part. */
export function partEnv(base: Record<string, string | undefined>, extra: Record<string, string>): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [key, value] of Object.entries(base)) {
    if (value !== undefined && ENV_ALLOW.test(key)) env[key] = value;
  }
  // a NODE_OPTIONS of the shell is replaced by the cap of the part, never appended to: the cap is the point
  return { ...env, NO_COLOR: "1", FORCE_COLOR: "0", PYTHONUNBUFFERED: "1", ...extra };
}

export interface ServiceStatus {
  id: PartId;
  state: State;
  port: number;
  pid: number | null;
  exitCode: number | null;
  signal: string | null;
  message: string;
  startedAt: number | null;
}

export interface SupervisorOptions {
  root: string;
  services?: ServiceDef[];
  env?: Record<string, string | undefined>;
  probeIntervalMs?: number;
  stopGraceMs?: number;
  /** lines kept per part */
  ringSize?: number;
  /** a message when a part must not start now (memory), else null */
  startGuard?: () => string | null;
}

interface Runtime {
  def: ServiceDef;
  child: ChildProcess | null;
  state: State;
  exitCode: number | null;
  signal: string | null;
  message: string;
  startedAt: number | null;
  stopRequested: boolean;
  busy: boolean;
  listening: boolean;
  lines: string[];
  partial: string;
  mask: (line: string) => string;
}

const MAX_LINE = 2000;

export class Supervisor extends EventEmitter {
  private readonly rt = new Map<PartId, Runtime>();
  private readonly root: string;
  private readonly env: Record<string, string | undefined>;
  private readonly ringSize: number;
  private readonly stopGraceMs: number;
  private readonly startGuard: () => string | null;
  private timer: NodeJS.Timeout | null = null;
  private closed = false;

  constructor(options: SupervisorOptions) {
    super();
    this.root = options.root;
    this.env = options.env ?? process.env;
    this.ringSize = options.ringSize ?? 500;
    this.stopGraceMs = options.stopGraceMs ?? 8000;
    this.startGuard = options.startGuard ?? (() => null);
    for (const def of options.services ?? defaultServices()) {
      this.rt.set(def.id, {
        def,
        child: null,
        state: "stopped",
        exitCode: null,
        signal: null,
        message: "",
        startedAt: null,
        stopRequested: false,
        busy: false,
        listening: false,
        lines: [],
        partial: "",
        mask: createMasker([]),
      });
    }
    void this.probeAll();
    this.timer = setInterval(() => void this.probeAll(), options.probeIntervalMs ?? 1500);
    this.timer.unref();
  }

  ids(): PartId[] {
    return [...this.rt.keys()];
  }

  private get(id: string): Runtime | undefined {
    return this.rt.get(id as PartId);
  }

  has(id: string): boolean {
    return this.rt.has(id as PartId);
  }

  status(): ServiceStatus[] {
    return [...this.rt.values()].map((r) => ({
      id: r.def.id,
      state: r.state,
      port: r.def.port,
      pid: r.child?.pid ?? null,
      exitCode: r.exitCode,
      signal: r.signal,
      message: r.message,
      startedAt: r.startedAt,
    }));
  }

  logs(id: string): string[] {
    return [...(this.get(id)?.lines ?? [])];
  }

  private setState(r: Runtime, state: State, message = r.message): void {
    if (r.state === state && r.message === message) return;
    r.state = state;
    r.message = message;
    this.emit("state", this.status());
  }

  private pushLine(r: Runtime, line: string, mask: (s: string) => string): void {
    const text = mask(line).slice(0, MAX_LINE);
    r.lines.push(text);
    if (r.lines.length > this.ringSize) r.lines.splice(0, r.lines.length - this.ringSize);
    this.emit("log", r.def.id, text);
  }

  /** Console's own message in the part's log, so the person sees what the console did. */
  private note(r: Runtime, text: string): void {
    this.pushLine(r, `[console] ${text}`, r.mask);
  }

  private probe(port: number): Promise<boolean> {
    return new Promise((resolve) => {
      const socket = net.connect({ host: "127.0.0.1", port });
      const done = (ok: boolean) => {
        socket.destroy();
        resolve(ok);
      };
      socket.setTimeout(400, () => done(false));
      socket.once("connect", () => done(true));
      socket.once("error", () => done(false));
    });
  }

  private async probeAll(): Promise<void> {
    if (this.closed) return;
    await Promise.all(
      [...this.rt.values()].map(async (r) => {
        const up = await this.probe(r.def.port);
        r.listening = up;
        if (r.busy) return;
        if (r.child) {
          if (up && r.state !== "running") this.setState(r, "running", "");
        } else if (up) {
          this.setState(r, "external", "démarré hors de la console (un terminal ?) : arrête-le là où il tourne");
        } else if (r.state === "external" || r.state === "running" || r.state === "starting") {
          this.setState(r, "stopped", "");
        }
      }),
    );
  }

  /** Why the part cannot start now, or null. */
  private blocker(r: Runtime): string | null {
    const dir = path.join(this.root, r.def.dir);
    if (!existsSync(dir)) return `pas de dossier ${r.def.dir}/ dans ce projet.`;
    for (const need of r.def.needs) {
      if (!existsSync(path.join(dir, need.path))) return need.message;
    }
    return null;
  }

  async start(id: string): Promise<{ ok: boolean; message: string }> {
    const r = this.get(id);
    if (!r) return { ok: false, message: "partie inconnue" };
    if (r.busy) return { ok: false, message: "une action est déjà en cours sur cette partie" };
    if (r.child) return { ok: true, message: "déjà lancée" };
    r.busy = true;
    try {
      const why = this.blocker(r);
      if (why) {
        this.setState(r, "blocked", why);
        this.note(r, why);
        return { ok: false, message: why };
      }
      const tight = this.startGuard();
      if (tight) {
        this.note(r, tight);
        return { ok: false, message: tight };
      }
      if (await this.probe(r.def.port)) {
        const message = `le port ${r.def.port} est déjà utilisé : arrête le serveur qui tourne dans un terminal.`;
        this.setState(r, "external", message);
        return { ok: false, message };
      }
      this.launch(r);
      return { ok: true, message: "lancée" };
    } finally {
      r.busy = false;
    }
  }

  private launch(r: Runtime): void {
    const dir = path.join(this.root, r.def.dir);
    // api/.env values are masked in this part's output; the file is read at each start, never printed
    let secrets: string[] = [];
    try {
      secrets = secretValues(parseEnvFile(readFileSync(path.join(this.root, "api", ".env"), "utf8")));
    } catch {
      // no api/.env: nothing to mask
    }
    // the secret-looking variables the part is given (a registry token in UV_* or NPM_CONFIG_*) are masked too
    const env = partEnv(this.env, r.def.env);
    secrets = [...new Set([...secrets, ...secretValues(new Map(Object.entries(env)))])].sort((a, b) => b.length - a.length);
    const mask = createMasker(secrets);
    r.mask = mask;
    const command = path.isAbsolute(r.def.command) || !r.def.command.includes("/") ? r.def.command : path.join(dir, r.def.command);
    r.lines = r.lines.slice(-50); // keep the end of the previous run, so a crash stays readable after a restart
    r.exitCode = null;
    r.signal = null;
    r.stopRequested = false;
    r.partial = "";
    r.startedAt = Date.now();
    this.note(r, `lancement : ${r.def.command} ${r.def.args.join(" ")} (dossier ${r.def.dir}/)`);
    // detached: the part leads its own process group, so one signal stops it and its children (esbuild, the reload worker)
    const child = spawn(command, r.def.args, {
      cwd: dir,
      env,
      detached: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    r.child = child;
    // First victim when the sandbox runs out of memory: a dev server, never the workspace agent (best effort: raising the score of our own
    // child is allowed without privilege; its children inherit it).
    if (child.pid !== undefined) {
      try {
        writeFileSync(`/proc/${child.pid}/oom_score_adj`, "500");
      } catch {
        // no /proc (not Linux) or not allowed
      }
    }
    this.setState(r, "starting", "");
    const onData = (chunk: Buffer) => {
      r.partial += chunk.toString("utf8");
      let newline = r.partial.indexOf("\n");
      while (newline >= 0) {
        this.pushLine(r, r.partial.slice(0, newline).replace(/\r$/, ""), mask);
        r.partial = r.partial.slice(newline + 1);
        newline = r.partial.indexOf("\n");
      }
      if (r.partial.length > MAX_LINE * 4) {
        this.pushLine(r, r.partial, mask);
        r.partial = "";
      }
    };
    child.stdout?.on("data", onData);
    child.stderr?.on("data", onData);
    child.once("error", (error) => {
      // spawn failed (no exit event follows): the part is not running
      this.note(r, `impossible de lancer la partie : ${error.message}`);
      if (r.child === child && child.pid === undefined) {
        r.child = null;
        this.setState(r, "crashed", "impossible de lancer la partie : lis le journal");
      }
    });
    child.once("exit", (code, signal) => {
      if (r.partial !== "") this.pushLine(r, r.partial, mask);
      r.partial = "";
      r.child = null;
      r.exitCode = code;
      r.signal = signal;
      const asked = r.stopRequested;
      this.note(r, asked ? "arrêtée." : `la partie s'est arrêtée (code ${code ?? "-"}${signal ? `, signal ${signal}` : ""}).`);
      // a crash while starting or running stays visible until the next start
      this.setState(r, asked || code === 0 ? "stopped" : "crashed", asked || code === 0 ? "" : `arrêtée toute seule (code ${code ?? "-"}${signal ? `, ${signal}` : ""}) : lis le journal`);
    });
  }

  private groupAlive(pid: number): boolean {
    try {
      process.kill(-pid, 0);
      return true;
    } catch {
      return false;
    }
  }

  async stop(id: string): Promise<{ ok: boolean; message: string }> {
    const r = this.get(id);
    if (!r) return { ok: false, message: "partie inconnue" };
    if (r.busy) return { ok: false, message: "une action est déjà en cours sur cette partie" };
    const child = r.child;
    if (!child || child.pid === undefined) {
      if (r.state === "external") return { ok: false, message: "cette partie n'a pas été lancée par la console : arrête-la dans son terminal" };
      return { ok: true, message: "déjà arrêtée" };
    }
    r.busy = true;
    try {
      await this.terminate(r, child);
      return { ok: true, message: "arrêtée" };
    } finally {
      r.busy = false;
    }
  }

  private async terminate(r: Runtime, child: ChildProcess): Promise<void> {
    const pid = child.pid as number;
    r.stopRequested = true;
    const exited = new Promise<void>((resolve) => {
      if (r.child === null) resolve();
      else child.once("exit", () => resolve());
    });
    // the whole group, never a single pid: the group id is the pid of the leader we spawned (detached)
    try {
      process.kill(-pid, "SIGTERM");
    } catch {
      // already gone
    }
    const timeout = new Promise<void>((resolve) => setTimeout(resolve, this.stopGraceMs).unref());
    await Promise.race([exited, timeout]);
    if (this.groupAlive(pid)) {
      try {
        process.kill(-pid, "SIGKILL");
      } catch {
        // gone in between
      }
      await Promise.race([exited, new Promise<void>((resolve) => setTimeout(resolve, 2000).unref())]);
    }
    // children that outlived the leader (the leader exited on SIGTERM, a worker did not)
    if (this.groupAlive(pid)) {
      try {
        process.kill(-pid, "SIGKILL");
      } catch {
        // gone in between
      }
    }
    // wait for the port to be released so that a restart can bind it again
    for (let i = 0; i < 20 && (await this.probe(r.def.port)); i++) await new Promise((resolve) => setTimeout(resolve, 250));
  }

  async restart(id: string): Promise<{ ok: boolean; message: string }> {
    const r = this.get(id);
    if (!r) return { ok: false, message: "partie inconnue" };
    if (r.state === "external") return { ok: false, message: "cette partie n'a pas été lancée par la console : arrête-la dans son terminal" };
    if (r.child) {
      const stopped = await this.stop(id);
      if (!stopped.ok) return stopped;
    }
    return this.start(id);
  }

  /** Stops every part the console started, then the probe. Called when the console ends. */
  async close(): Promise<void> {
    this.closed = true;
    if (this.timer) clearInterval(this.timer);
    await Promise.all([...this.rt.values()].map(async (r) => {
      if (r.child) await this.terminate(r, r.child);
    }));
  }
}
