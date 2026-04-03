import assert from "node:assert/strict";
import test from "node:test";

import { toUnknownRecord, toUnknownRecordArray } from "./records";

test("toUnknownRecord returns null for primitives and arrays", () => {
  assert.equal(toUnknownRecord(null), null);
  assert.equal(toUnknownRecord("value"), null);
  assert.equal(toUnknownRecord(["a", "b"]), null);
});

test("toUnknownRecord returns objects unchanged", () => {
  assert.deepEqual(toUnknownRecord({ id: "1", name: "bank" }), {
    id: "1",
    name: "bank",
  });
});

test("toUnknownRecordArray filters out non-object items", () => {
  assert.deepEqual(
    toUnknownRecordArray([{ id: 1 }, null, "text", { id: 2, active: true }]),
    [{ id: 1 }, { id: 2, active: true }],
  );
});

test("toUnknownRecordArray returns empty array for non-arrays", () => {
  assert.deepEqual(toUnknownRecordArray(undefined), []);
  assert.deepEqual(toUnknownRecordArray({ id: 1 }), []);
});
