import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

// The worker is a pre-bundled copy of maplibre-gl's worker (src/assets/maplibre-gl-worker.bundled.js).
// If its version differs from the installed maplibre-gl, the map throws
// "can't deserialize unregistered class StructArrayLayout..." and draws nothing.
test("the bundled maplibre worker is the version of the installed maplibre-gl", () => {
  const installed = JSON.parse(
    readFileSync(
      new URL("../miniapp/node_modules/maplibre-gl/package.json", import.meta.url),
      "utf8",
    ),
  ) as { version: string };
  const worker = readFileSync(
    new URL("../miniapp/src/assets/maplibre-gl-worker.bundled.js", import.meta.url),
    "utf8",
  );
  assert.match(worker, new RegExp(`maplibre-gl-js/blob/v${installed.version.replaceAll(".", "\\.")}/`));
});

test("the bundled maplibre worker is a classic script (no module syntax)", () => {
  const worker = readFileSync(
    new URL("../miniapp/src/assets/maplibre-gl-worker.bundled.js", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(worker, /^\s*(import|export)\s/m);
});
