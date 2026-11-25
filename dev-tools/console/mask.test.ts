// Run by `npm test` in miniapp/ (node's own test runner, no dependency).
import assert from "node:assert/strict";
import { test } from "node:test";
import { createMasker, parseEnvFile, secretValues } from "./mask.ts";

const ENV = `# comment
ENVIRONMENT=development
DATABASE_URL=postgresql://role:S3cretPass99@db.internal:5432/up_dev
export CACHE_KEY_PREFIX="up-dev-demo:"
STORAGE_SECRET_KEY='abcdef123456'
SHORT_TOKEN=abc
PORT_LIKE=21514
QUOTED_SPACE="a b c d e f g"   # trailing
`;

test("parseEnvFile reads plain, quoted and exported values", () => {
  const pairs = parseEnvFile(ENV);
  assert.equal(pairs.get("ENVIRONMENT"), "development");
  assert.equal(pairs.get("CACHE_KEY_PREFIX"), "up-dev-demo:");
  assert.equal(pairs.get("STORAGE_SECRET_KEY"), "abcdef123456");
  assert.equal(pairs.get("QUOTED_SPACE"), "a b c d e f g");
  assert.equal(pairs.has("# comment"), false);
});

test("secretValues keeps long secret-looking values and URL passwords, not plain settings", () => {
  const values = secretValues(parseEnvFile(ENV));
  assert.ok(values.includes("abcdef123456"));
  assert.ok(values.includes("S3cretPass99"));
  assert.ok(values.includes("postgresql://role:S3cretPass99@db.internal:5432/up_dev"));
  assert.ok(!values.includes("development"), "ENVIRONMENT is not a secret");
  assert.ok(!values.includes("abc"), "too short to mask");
  assert.ok(!values.includes("21514"));
  // longest first: the whole URL is replaced before its password alone
  assert.ok(values.indexOf("postgresql://role:S3cretPass99@db.internal:5432/up_dev") < values.indexOf("S3cretPass99"));
});

test("the masker hides values, URL passwords, JWTs and bearer tokens, and strips colours", () => {
  const mask = createMasker(secretValues(parseEnvFile(ENV)));
  assert.equal(mask("connect to postgresql://role:S3cretPass99@db.internal:5432/up_dev failed"), "connect to *** failed");
  assert.equal(mask("password S3cretPass99 rejected"), "password *** rejected");
  assert.equal(mask("key=abcdef123456"), "key=***");
  assert.equal(mask("mysql://u:hunter2hunter2@host/x"), "mysql://u:***@host/x");
  assert.equal(mask("Authorization: Bearer abcdef0123456789abcdef"), "Authorization: Bearer ***");
  assert.equal(mask("t=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"), "t=***");
  assert.equal(mask("\u001b[32mready\u001b[39m in 300 ms"), "ready in 300 ms");
  assert.equal(mask("ENVIRONMENT=development"), "ENVIRONMENT=development");
});
