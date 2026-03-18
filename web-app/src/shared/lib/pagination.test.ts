import assert from "node:assert/strict";
import test from "node:test";

import {
  getPaginationFromSearchParams,
  normalizePage,
  toBackendPageQuery,
} from "./pagination";

test("normalizePage fills missing values with defaults", () => {
  assert.deepEqual(normalizePage(null), {
    content: [],
    totalElements: 0,
    totalPages: 0,
    number: 0,
    size: 0,
    numberOfElements: 0,
    first: true,
    last: true,
    empty: true,
  });
});

test("getPaginationFromSearchParams parses valid values and sort arrays", () => {
  const result = getPaginationFromSearchParams(
    {
      page: "2",
      size: "25",
      sort: ["createdAt,desc", "name,asc"],
    },
    { page: 0, size: 10 },
  );

  assert.deepEqual(result, {
    page: 2,
    size: 25,
    sort: ["createdAt,desc", "name,asc"],
  });
});

test("getPaginationFromSearchParams falls back on invalid values", () => {
  const result = getPaginationFromSearchParams(
    {
      page: "-1",
      size: "oops",
    },
    { page: 1, size: 20 },
  );

  assert.deepEqual(result, {
    page: 1,
    size: 20,
    sort: undefined,
  });
});

test("toBackendPageQuery applies backend defaults", () => {
  assert.deepEqual(toBackendPageQuery({}), {
    page: 0,
    size: 10,
    sort: undefined,
  });
});
