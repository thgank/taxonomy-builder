import assert from "node:assert/strict";
import test from "node:test";

import { createJobSchema, parseJobParams } from "./create-job-schema";

test("createJobSchema accepts empty params and valid JSON object", () => {
  const empty = createJobSchema.safeParse({
    type: "FULL_PIPELINE",
    paramsText: "   ",
  });
  const valid = createJobSchema.safeParse({
    type: "IMPORT",
    paramsText: ' { "chunk_size": 200 } ',
  });

  assert.equal(empty.success, true);
  assert.equal(valid.success, true);
});

test("createJobSchema rejects invalid JSON and non-object payloads", () => {
  const invalidJson = createJobSchema.safeParse({
    type: "IMPORT",
    paramsText: "{nope",
  });
  const invalidShape = createJobSchema.safeParse({
    type: "IMPORT",
    paramsText: '["not","object"]',
  });

  assert.equal(invalidJson.success, false);
  assert.equal(invalidShape.success, false);
});

test("parseJobParams returns empty object or parsed JSON", () => {
  assert.deepEqual(parseJobParams("   "), {});
  assert.deepEqual(parseJobParams('{"max_terms":50}'), { max_terms: 50 });
});

