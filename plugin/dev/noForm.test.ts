import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

// The Studio runs the plugin in an iframe sandboxed without allow-forms: a form submission is
// blocked. Use buttons with onClick (ModalActions submitType="button").
test("no source file of the plugin uses a form element or a submit button", () => {
  const root = new URL("../src", import.meta.url).pathname;
  for (const file of sourceFiles(root)) {
    const code = readFileSync(file, "utf8").replace(/\/\/.*$/gm, "");
    assert.doesNotMatch(code, /<form[\s>]/, `${file} uses <form>`);
    assert.doesNotMatch(
      code,
      /type=["']submit["']/,
      `${file} has a submit button`,
    );
    assert.doesNotMatch(
      code,
      /requestSubmit|\.submit\(\)/,
      `${file} submits a form`,
    );
  }
});
