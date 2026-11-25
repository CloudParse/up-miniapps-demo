// Secret masking of the console's logs. The console never prints the value of a setting of api/.env, nor a token.
// The API and the Vite servers write their own output: a stack trace or a debug line can carry a connection string.

const MASK = "***";
// Keys whose value is masked wherever it appears in a line. Other keys (ENVIRONMENT=development, a port) stay readable.
const SECRET_KEY = /(SECRET|TOKEN|PASS|PWD|KEY|URL|DSN|CREDENTIAL|AUTH)/i;
// A value shorter than this is not masked: masking "1" or "true" would garble every line.
const MIN_LENGTH = 6;
// eslint-disable-next-line no-control-regex
const ANSI = /\u001b\[[0-9;?]*[ -/]*[@-~]/g;
const JWT = /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*/g;
const BEARER = /\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}/gi;
// user:password@ in any URL
const URL_PASSWORD = /(\b[a-z][a-z0-9+.-]*:\/\/[^\s:/@]*:)[^\s@/]+(@)/gi;

/** The KEY=VALUE pairs of an env file, as `python -m app` reads them: plain values, optional quotes, `export`, comments. */
export function parseEnvFile(text: string): Map<string, string> {
  const pairs = new Map<string, string>();
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (line === "" || line.startsWith("#")) continue;
    const match = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line);
    if (!match) continue;
    let value = (match[2] ?? "").trim();
    const quoted = /^(["'])(.*?)\1(?:\s+#.*)?$/.exec(value);
    value = quoted ? (quoted[2] as string) : value.replace(/\s+#.*$/, "");
    pairs.set(match[1] as string, value);
  }
  return pairs;
}

/** The values to hide: the secret-looking values of an env file, longest first so a long value is not half masked by a short one. */
export function secretValues(pairs: Map<string, string>): string[] {
  const values = new Set<string>();
  for (const [key, value] of pairs) {
    if (value.length >= MIN_LENGTH && SECRET_KEY.test(key)) values.add(value);
    // the password of a URL value is hidden alone too: a log line often carries the host without the whole URL
    for (const m of value.matchAll(/:\/\/[^\s:/@]*:([^\s@/]+)@/g)) {
      const password = m[1] as string;
      if (password.length >= MIN_LENGTH) values.add(password);
    }
  }
  return [...values].sort((a, b) => b.length - a.length);
}

/** Builds the line masker: ANSI colours removed, the given secret values, JWTs, Bearer/Basic credentials, URL passwords. */
export function createMasker(secrets: readonly string[]): (line: string) => string {
  return (line: string): string => {
    let out = line.replace(ANSI, "");
    for (const secret of secrets) out = out.split(secret).join(MASK);
    return out
      .replace(JWT, MASK)
      .replace(BEARER, `$1 ${MASK}`)
      .replace(URL_PASSWORD, `$1${MASK}$2`);
  };
}
