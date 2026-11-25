import assert from "node:assert/strict";
import { test } from "node:test";
import { acceptKey, textFrame } from "./ws.ts";

test("acceptKey is the RFC 6455 example", () => {
  assert.equal(acceptKey("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=");
});

test("textFrame: 7-bit, 16-bit and 64-bit lengths", () => {
  const small = textFrame("hi");
  assert.deepEqual([...small], [0x81, 2, 0x68, 0x69]);
  const medium = textFrame("x".repeat(300));
  assert.deepEqual([...medium.subarray(0, 4)], [0x81, 126, 1, 44]);
  assert.equal(medium.length, 304);
  const large = textFrame("y".repeat(70000));
  assert.equal(large[1], 127);
  assert.equal(large.readBigUInt64BE(2), 70000n);
  assert.equal(large.length, 10 + 70000);
});
