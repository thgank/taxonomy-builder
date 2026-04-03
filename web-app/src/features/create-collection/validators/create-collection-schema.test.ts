import assert from "node:assert/strict";
import test from "node:test";

import { createCollectionSchema } from "./create-collection-schema";

test("createCollectionSchema trims input and accepts valid payload", () => {
  const parsed = createCollectionSchema.parse({
    name: "  Energy  ",
    description: "  Domain documents  ",
  });

  assert.deepEqual(parsed, {
    name: "Energy",
    description: "Domain documents",
  });
});

test("createCollectionSchema rejects empty names and oversized descriptions", () => {
  const empty = createCollectionSchema.safeParse({
    name: "   ",
    description: "ok",
  });
  const oversized = createCollectionSchema.safeParse({
    name: "Energy",
    description: "x".repeat(4001),
  });

  assert.equal(empty.success, false);
  assert.equal(oversized.success, false);
});

