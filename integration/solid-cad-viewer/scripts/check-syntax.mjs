// Syntax-only validation; deliberately NOT a substitute for a full dependency-aware typecheck.
import { createRequire } from "node:module";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);
const ts = process.env.TYPESCRIPT_PATH ? require(process.env.TYPESCRIPT_PATH) : require("typescript");
let files = 0;
let errors = 0;
function check(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (!["node_modules", ".core-build", "dist", ".git"].includes(entry.name)) check(target);
    } else if (/\.tsx?$/.test(entry.name)) {
      const source = ts.createSourceFile(target, readFileSync(target, "utf8"), ts.ScriptTarget.Latest, true,
        target.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
      files++;
      for (const diagnostic of source.parseDiagnostics) {
        errors++;
        console.error(ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"), target);
      }
    }
  }
}
check(process.cwd());
console.log(`Parsed ${files} TypeScript/TSX files; ${errors} syntax diagnostics. This does not check external APIs.`);
process.exitCode = errors ? 1 : 0;
