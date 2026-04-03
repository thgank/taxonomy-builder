import assert from "node:assert/strict";
import test from "node:test";

import {
  getFiles,
  getOptionalBoolean,
  getOptionalNumber,
  getOptionalString,
  getString,
} from "./form-data";

test("getString trims string values and ignores non-string entries", () => {
  const formData = new FormData();
  formData.set("name", "  Energy system  ");
  formData.set("fileLike", new File(["content"], "report.txt"));

  assert.equal(getString(formData, "name"), "Energy system");
  assert.equal(getString(formData, "missing"), "");
  assert.equal(getString(formData, "fileLike"), "");
});

test("optional helpers return undefined for empty and invalid values", () => {
  const formData = new FormData();
  formData.set("description", "   ");
  formData.set("size", "12.5");
  formData.set("badSize", "NaN-ish");
  formData.set("enabled", "on");

  assert.equal(getOptionalString(formData, "description"), undefined);
  assert.equal(getOptionalNumber(formData, "size"), 12.5);
  assert.equal(getOptionalNumber(formData, "badSize"), undefined);
  assert.equal(getOptionalNumber(formData, "missing"), undefined);
  assert.equal(getOptionalBoolean(formData, "enabled"), true);
  assert.equal(getOptionalBoolean(formData, "disabled"), undefined);
});

test("getFiles keeps only non-empty File objects", () => {
  const formData = new FormData();
  formData.append("files", new File(["alpha"], "a.txt"));
  formData.append("files", new File([], "empty.txt"));
  formData.append("files", "not-a-file");

  const files = getFiles(formData, "files");

  assert.equal(files.length, 1);
  assert.equal(files[0]?.name, "a.txt");
});

