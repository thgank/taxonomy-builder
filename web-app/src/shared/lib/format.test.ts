import assert from "node:assert/strict";
import test from "node:test";

import {
  formatDateTime,
  formatFileSize,
  formatJsonCompact,
  pluralize,
} from "./format";

test("formatDateTime returns fallback for missing values", () => {
  assert.equal(formatDateTime(null), "Not available");
  assert.equal(formatDateTime(undefined), "Not available");
});

test("formatDateTime formats a valid ISO timestamp", () => {
  assert.match(formatDateTime("2026-04-03T08:00:00Z"), /\w{3} \d{1,2}, 2026/);
});

test("formatFileSize formats bytes and kilobytes", () => {
  assert.equal(formatFileSize(0), "0 B");
  assert.equal(formatFileSize(512), "512 B");
  assert.equal(formatFileSize(1536), "1.5 KB");
  assert.equal(formatFileSize(5 * 1024 * 1024), "5.0 MB");
});

test("formatJsonCompact reports empty parameters", () => {
  assert.equal(formatJsonCompact(undefined), "No parameters");
  assert.equal(formatJsonCompact({}), "No parameters");
  assert.equal(formatJsonCompact({ mode: "hybrid" }), '{\n  "mode": "hybrid"\n}');
});

test("pluralize selects singular and plural forms", () => {
  assert.equal(pluralize(1, "document", "documents"), "1 document");
  assert.equal(pluralize(3, "document", "documents"), "3 documents");
});
