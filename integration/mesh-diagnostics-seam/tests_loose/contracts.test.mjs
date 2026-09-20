import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { parseDocument, PayloadError } from "../.core-build/loose/contracts.js";

const fixture = JSON.parse(readFileSync(new URL("./source-face-id-cases.json", import.meta.url), "utf8"));
for (const item of fixture.cases) {
  test(item.name, () => {
    const raw = structuredClone(fixture.document);
    raw.meshes[0].triangle_source_faces = item.mapping;
    if (item.valid) {
      assert.deepEqual(parseDocument(raw).meshes[0].triangle_source_faces, item.mapping);
    } else {
      assert.throws(() => parseDocument(raw), PayloadError);
    }
  });
}
