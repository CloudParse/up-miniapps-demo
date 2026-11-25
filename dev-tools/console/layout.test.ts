// The layout logic of the console page (which parts of the page are visible) lives inline in page.html, which the console serves
// as one file. This test cuts it out between its two markers and runs it in an empty context.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const page = readFileSync(new URL("./page.html", import.meta.url), "utf8");
const block = page.split("// layout-logic:begin")[1]?.split("// layout-logic:end")[0];
assert.ok(block, "layout-logic markers are in page.html");
const { parseLayout, reduceLayout, DEFAULT_LAYOUT } = vm.runInNewContext(`${block}; ({ parseLayout, reduceLayout, DEFAULT_LAYOUT })`) as {
  parseLayout: (raw: string | null) => { cards: boolean; logs: boolean; full: boolean };
  reduceLayout: (s: { cards: boolean; logs: boolean; full: boolean }, a: string) => { cards: boolean; logs: boolean; full: boolean };
  DEFAULT_LAYOUT: { cards: boolean; logs: boolean; full: boolean };
};
const plain = (v: unknown) => JSON.parse(JSON.stringify(v));

test("default: services shown, logs closed, not full screen", () => {
  assert.deepEqual(plain(DEFAULT_LAYOUT), { cards: true, logs: false, full: false });
  assert.deepEqual(plain(parseLayout(null)), plain(DEFAULT_LAYOUT));
  assert.deepEqual(plain(parseLayout("not json")), plain(DEFAULT_LAYOUT));
});

test("a stored choice is restored, never the full screen", () => {
  assert.deepEqual(plain(parseLayout('{"cards":false,"logs":true,"full":true}')), { cards: false, logs: true, full: false });
  assert.deepEqual(plain(parseLayout('{"cards":"yes"}')), { cards: true, logs: false, full: false });
});

test("toggles flip one part", () => {
  const hidden = reduceLayout(DEFAULT_LAYOUT, "cards");
  assert.equal(hidden.cards, false);
  assert.equal(reduceLayout(hidden, "cards").cards, true);
  assert.equal(reduceLayout(DEFAULT_LAYOUT, "logs").logs, true);
});

test("full screen keeps the choice, Escape restores it", () => {
  const before = { cards: true, logs: true, full: false };
  const full = reduceLayout(before, "full");
  assert.equal(full.full, true);
  assert.deepEqual(plain(reduceLayout(full, "escape")), before);
  assert.deepEqual(plain(reduceLayout(full, "full")), before);
});

test("Escape closes the logs when not full screen, else does nothing", () => {
  assert.equal(reduceLayout({ cards: true, logs: true, full: false }, "escape").logs, false);
  assert.deepEqual(plain(reduceLayout(DEFAULT_LAYOUT, "escape")), plain(DEFAULT_LAYOUT));
});

test("a toggle during full screen leaves it and shows that part alone", () => {
  assert.deepEqual(plain(reduceLayout({ cards: false, logs: false, full: true }, "cards")), { cards: true, logs: false, full: false });
  assert.deepEqual(plain(reduceLayout({ cards: true, logs: false, full: true }, "logs")), { cards: false, logs: true, full: false });
});

test("the page has the accessible toggles", () => {
  for (const id of ["tog-cards", "tog-logs", "tog-full"]) assert.match(page, new RegExp(`id="${id}"`));
  assert.match(page, /id="tog-cards"[^>]*aria-expanded/);
  assert.match(page, /id="tog-logs"[^>]*aria-expanded/);
  assert.match(page, /aria-label/);
});
