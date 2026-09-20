import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
const compiler = process.platform === "win32" ? "tsc.cmd" : "tsc";
execFileSync(compiler, ["-p", "tsconfig.core.json"], { stdio: "inherit", shell: process.platform === "win32" });
mkdirSync(".core-build", { recursive: true });
writeFileSync(".core-build/package.json", JSON.stringify({ type: "commonjs" }));
execFileSync(process.execPath, ["--test", "tests/core.test.mjs"], { stdio: "inherit" });
