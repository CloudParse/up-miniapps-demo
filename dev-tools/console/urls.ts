// The addresses of the three parts and of the console, in a Coder workspace and on a laptop.
// In a workspace, VSCODE_PROXY_URI is the port URL template: https://{{port}}--<agent>--<workspace>--<owner>--<org>.<apps domain>/.
// The Coder buttons have no agent name: <slug>--<workspace>--<owner>--<org>.<apps domain> (docs/coder.md, "Where to open the mini-app").
// The port URLs (21515--main--...) do not open the pages: only the button addresses are built here.

export type PartId = "api" | "miniapp" | "plugin";
export const PORTS: Record<PartId | "console", number> = { api: 21514, miniapp: 21515, plugin: 21516, console: 21513 };

/** The button address of an app slug (`miniapp`, `api`, `plugin`, `console`), or null outside a Coder workspace with an apps domain. */
export function buttonUrl(slug: string, env: Record<string, string | undefined> = process.env): string | null {
  const proxy = env.VSCODE_PROXY_URI;
  if (!proxy) return null;
  const agent = env.CODER_WORKSPACE_AGENT_NAME || "main";
  const prefix = `{{port}}--${agent}--`;
  if (!proxy.includes(prefix)) return null;
  try {
    return new URL(proxy.replace(prefix, `${slug}--`)).origin + "/";
  } catch {
    return null;
  }
}

export interface PartUrls {
  /** where the part answers for the person's browser: the Coder button, or localhost on a laptop; "" when Coder has no apps domain */
  open: string;
  /** same origin, the page that proves the part works (the API docs); "" like open */
  page: string;
}

/** The links of one part. Outside Coder (no VSCODE_PROXY_URI): localhost. In Coder without an apps domain: empty (use the workspace page). */
export function partUrls(id: PartId, env: Record<string, string | undefined> = process.env): PartUrls {
  const suffix = id === "api" ? "docs" : "";
  const button = buttonUrl(id, env);
  if (button) return { open: button, page: button + suffix };
  if (env.VSCODE_PROXY_URI) return { open: "", page: "" };
  const local = `http://localhost:${PORTS[id]}/`;
  return { open: local, page: local + suffix };
}
