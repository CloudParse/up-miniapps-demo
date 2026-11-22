// Development only, shared by miniapp/vite.config.ts and plugin/vite.dev.config.ts.
//
// Vite answers any IPv4 or IPv6 Host header before it looks at `allowedHosts`, so with
// `server.host: true` a request with `Host: 10.0.0.5:21515` would pass. This guard
// rejects every Host (IP addresses included) that is not in the list, with a 403.
// The dev servers listen on 0.0.0.0 so Coder lists their ports: this is what keeps
// other machines out when they reach the port with their own Host header.

const LOOPBACK_HOSTS = ["localhost", "127.0.0.1", "[::1]"];

// Only the parts of Vite's types this file uses: the folder has no node_modules of its own.
interface Request {
  headers: { host?: string };
}
interface Response {
  end(body: string): void;
  setHeader(name: string, value: string): void;
  statusCode: number;
}
interface DevServer {
  middlewares: {
    use(handler: (req: Request, res: Response, next: () => void) => void): void;
  };
}

/** The host name of a Host header, lowercase, without its port: `[::1]:21515` gives `[::1]`. */
export function hostNameOf(header: string | undefined): string {
  const value = (header ?? "").trim().toLowerCase();
  if (value.startsWith("[")) return value.slice(0, value.indexOf("]") + 1);
  return value.split(":")[0] ?? "";
}

/**
 * Whether `header` names an allowed host. An entry that starts with a dot allows its
 * subdomains (`.example.com`), as in Vite's `allowedHosts`.
 */
export function isAllowedHost(
  header: string | undefined,
  allowed: readonly string[],
): boolean {
  const name = hostNameOf(header);
  if (name === "") return false;
  return [...LOOPBACK_HOSTS, ...allowed].some((entry) => {
    const host = entry.toLowerCase();
    return host.startsWith(".")
      ? name.endsWith(host) || name === host.slice(1)
      : name === host;
  });
}

/**
 * The names the guard allows beyond the loopback ones: `DEV_ALLOWED_HOSTS` (comma
 * separated), the Coder port URL host of `port` (`VSCODE_PROXY_URI`) and `extra`.
 */
export function devAllowedHosts(
  port: number,
  env: Record<string, string | undefined> = process.env,
  extra: readonly string[] = [],
): string[] {
  const hosts = (env.DEV_ALLOWED_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim())
    .filter((host) => host.length > 0);
  const coderProxy = env.VSCODE_PROXY_URI;
  if (coderProxy) {
    // An unusable VSCODE_PROXY_URI (no scheme, garbage) must not stop the dev server with
    // "Invalid URL": the loopback names and DEV_ALLOWED_HOSTS still work.
    try {
      hosts.push(new URL(coderProxy.replace("{{port}}", String(port))).hostname);
    } catch {
      // ignored
    }
  }
  return [...hosts, ...extra];
}

/** Vite plugin: 403 for every request whose Host header is not allowed. */
export function hostGuard(allowed: readonly string[]) {
  return {
    configureServer(server: DevServer) {
      server.middlewares.use((req, res, next) => {
        if (isAllowedHost(req.headers.host, allowed)) {
          next();
          return;
        }
        res.statusCode = 403;
        res.setHeader("Content-Type", "text/plain");
        res.end(
          "Blocked request: this host is not allowed (DEV_ALLOWED_HOSTS).",
        );
      });
    },
    name: "up-dev-host-guard",
  };
}
