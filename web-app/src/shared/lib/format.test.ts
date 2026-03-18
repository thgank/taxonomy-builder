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

test("formatFileSize formats bytes and kilobytes", () => {
  assert.equal(formatFileSize(0), "0 B");
  assert.equal(formatFileSize(512), "512 B");
  assert.equal(formatFileSize(1536), "1.5 KB");
});

test("formatJsonCompact reports empty parameters", () => {
  assert.equal(formatJsonCompact(undefined), "No parameters");
  assert.equal(formatJsonCompact({}), "No parameters");
});

test("pluralize selects singular and plural forms", () => {
  assert.equal(pluralize(1, "document", "documents"), "1 document");
  assert.equal(pluralize(3, "document", "documents"), "3 documents");
});
