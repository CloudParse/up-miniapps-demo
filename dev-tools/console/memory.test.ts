import assert from "node:assert/strict";
import { test } from "node:test";
import { parseMeminfo, startRefusal } from "./memory.ts";

const SAMPLE = "MemTotal:        2097152 kB\nMemFree:          100000 kB\nMemAvailable:     524288 kB\n";

test("parseMeminfo: total, available and used (total minus available)", () => {
  assert.deepEqual(parseMeminfo(SAMPLE), { totalMiB: 2048, availableMiB: 512, usedMiB: 1536 });
  assert.equal(parseMeminfo("nothing"), null);
});

test("startRefusal: refuses with the figures when little is free, never without a figure", () => {
  assert.equal(startRefusal({ totalMiB: 2048, availableMiB: 512, usedMiB: 1536 }), null);
  const refusal = startRefusal({ totalMiB: 2048, availableMiB: 120, usedMiB: 1928 });
  assert.match(refusal ?? "", /120 Mio libres sur 2048 Mio/);
  assert.equal(startRefusal(null), null);
});
