import assert from "node:assert/strict";
import { test } from "node:test";
import { getErrorMessage } from "../miniapp/src/lib/errors.ts";

test("a native-only capability on the web launcher gets a clear message", () => {
  assert.equal(
    getErrorMessage(
      new Error("GET_FIDELITY_BALANCE is not supported by the UP web host"),
    ),
    "Cette fonction n'existe que dans l'app UP, pas sur le site web.",
  );
});

test("other errors keep their message", () => {
  assert.equal(getErrorMessage(new Error("boom")), "boom");
  assert.equal(getErrorMessage("texte"), "texte");
  assert.equal(getErrorMessage({ error: "interne" }), "interne");
  assert.equal(getErrorMessage(42), "Une erreur inattendue est survenue.");
});
