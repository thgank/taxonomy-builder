import assert from "node:assert/strict";
import test from "node:test";

function loadServerEnv() {
  const modulePath = require.resolve("./env");
  delete require.cache[modulePath];
  return require("./env") as { serverEnv: { TAXONOMY_API_BASE_URL: string; TAXONOMY_API_KEY: string } };
}

test("serverEnv parses valid environment variables", () => {
  const previousBaseUrl = process.env.TAXONOMY_API_BASE_URL;
  const previousApiKey = process.env.TAXONOMY_API_KEY;

  process.env.TAXONOMY_API_BASE_URL = "https://taxonomy.example/api/";
  process.env.TAXONOMY_API_KEY = "test-key";

  const { serverEnv } = loadServerEnv();

  assert.equal(serverEnv.TAXONOMY_API_BASE_URL, "https://taxonomy.example/api/");
  assert.equal(serverEnv.TAXONOMY_API_KEY, "test-key");

  process.env.TAXONOMY_API_BASE_URL = previousBaseUrl;
  process.env.TAXONOMY_API_KEY = previousApiKey;
});

test("serverEnv throws when required values are missing", () => {
  const previousBaseUrl = process.env.TAXONOMY_API_BASE_URL;
  const previousApiKey = process.env.TAXONOMY_API_KEY;

  delete process.env.TAXONOMY_API_BASE_URL;
  process.env.TAXONOMY_API_KEY = "";

  assert.throws(() => loadServerEnv());

  process.env.TAXONOMY_API_BASE_URL = previousBaseUrl;
  process.env.TAXONOMY_API_KEY = previousApiKey;
});
