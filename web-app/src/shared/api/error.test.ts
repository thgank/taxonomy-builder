import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, isApiError } from "./error";

test("ApiError preserves status and payload", () => {
  const error = new ApiError("Failed to fetch", 502, {
    status: 502,
    message: "Failed to fetch",
    timestamp: "2026-04-03T08:00:00Z",
  });

  assert.equal(error.name, "ApiError");
  assert.equal(error.message, "Failed to fetch");
  assert.equal(error.status, 502);
  assert.equal(error.payload?.timestamp, "2026-04-03T08:00:00Z");
});

test("isApiError narrows only ApiError instances", () => {
  assert.equal(isApiError(new ApiError("boom", 500)), true);
  assert.equal(isApiError(new Error("boom")), false);
  assert.equal(isApiError({ message: "boom" }), false);
});

