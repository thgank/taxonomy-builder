import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const reportsDir = path.join(rootDir, "reports");
const coverageLogPath = path.join(reportsDir, "coverage.log");
const minLine = Number.parseFloat(process.env.WEB_LINE_COVERAGE_MIN ?? "90");
const minBranch = Number.parseFloat(process.env.WEB_BRANCH_COVERAGE_MIN ?? "80");

await mkdir(reportsDir, { recursive: true });

const command = process.platform === "win32" ? "npm.cmd" : "npm";
const child = spawn(command, ["run", "test:coverage"], {
  cwd: rootDir,
  env: process.env,
  stdio: ["ignore", "pipe", "pipe"],
});

let output = "";

for (const stream of [child.stdout, child.stderr]) {
  stream.on("data", (chunk) => {
    const text = chunk.toString();
    output += text;
    process.stdout.write(text);
  });
}

const exitCode = await new Promise((resolve, reject) => {
  child.on("error", reject);
  child.on("close", resolve);
});

await writeFile(coverageLogPath, output, "utf8");

if (exitCode !== 0) {
  process.exit(exitCode ?? 1);
}

const summaryMatch = output.match(/all files\s+\|\s+([\d.]+)\s+\|\s+([\d.]+)/);
if (!summaryMatch) {
  console.error("Coverage summary not found in test output.");
  process.exit(1);
}

const linePct = Number.parseFloat(summaryMatch[1]);
const branchPct = Number.parseFloat(summaryMatch[2]);

if (linePct < minLine || branchPct < minBranch) {
  console.error(
    `Web coverage gate failed: line ${linePct.toFixed(2)}% (min ${minLine.toFixed(2)}%), ` +
      `branch ${branchPct.toFixed(2)}% (min ${minBranch.toFixed(2)}%).`,
  );
  process.exit(1);
}

console.log(
  `Web coverage gate passed: line ${linePct.toFixed(2)}%, branch ${branchPct.toFixed(2)}%.`,
);
