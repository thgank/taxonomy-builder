import assert from "node:assert/strict";
import test from "node:test";

import { cn } from "./cn";

test("cn merges class names and resolves tailwind conflicts", () => {
  assert.equal(cn("px-2", "py-1", "px-4"), "py-1 px-4");
  assert.equal(cn("text-sm", false && "hidden", undefined, "font-medium"), "text-sm font-medium");
});

