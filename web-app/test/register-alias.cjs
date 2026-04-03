const Module = require("node:module");
const path = require("node:path");

const projectRoot = process.cwd();
const originalResolveFilename = Module._resolveFilename;

Module._resolveFilename = function patchedResolve(request, parent, isMain, options) {
  if (request === "next/cache") {
    return path.join(projectRoot, "test", "stubs", "next-cache.cjs");
  }

  if (request === "server-only") {
    return path.join(projectRoot, "test", "stubs", "server-only.cjs");
  }

  if (request === "next/link") {
    return path.join(projectRoot, "test", "stubs", "next-link.cjs");
  }

  if (request.startsWith("@/")) {
    return path.join(projectRoot, ".test-dist", "src", `${request.slice(2)}.js`);
  }

  return originalResolveFilename.call(this, request, parent, isMain, options);
};
