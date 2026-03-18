import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import openapiTS from "openapi-typescript";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const inputPath = process.env.OPENAPI_SCHEMA_PATH ?? "/tmp/taxonomy-api-docs.json";
const outputPath = path.resolve(rootDir, "src/shared/api/generated/openapi.d.ts");

const schema = JSON.parse(await readFile(inputPath, "utf8"));
const contents = await openapiTS(schema);

await mkdir(path.dirname(outputPath), { recursive: true });
await writeFile(outputPath, contents, "utf8");

console.log(`Generated OpenAPI types from ${inputPath} to ${outputPath}`);
