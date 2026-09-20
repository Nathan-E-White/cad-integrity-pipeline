import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseDocument } from "../.core-build/core/contracts.js";
import { resolveTarget } from "../.core-build/core/selection.js";
import { frameFor, toDisplay } from "../.core-build/core/math.js";

const fixture = JSON.parse(readFileSync(new URL("../examples/torus-comparison.json", import.meta.url)));
test("Python fixture preserves two identities, unchecked status and shared world frame", () => {
  const value = parseDocument(fixture);
  assert.equal(value.meshes.length, 2);
  assert.equal(value.meshes[0].id, "before");
  assert.ok(value.meshes[0].metrics.some(m => m.status === "unknown"));
  const frame = frameFor(value.meshes);
  assert.deepEqual(toDisplay(frame.origin, frame), [0, 0, 0]);
});
test("selection cannot cross meshes or revisions", () => {
  const [before, after] = parseDocument(fixture).meshes;
  const target = { meshId: before.id, revision: before.revision, kind: "face", faceId: 0 };
  assert.deepEqual(resolveTarget(before, target).face_ids, [0]);
  assert.equal(resolveTarget(after, target), null);
  assert.equal(resolveTarget({...before, revision: "next"}, target), null);
});
test("null clears and invalid geometry does not become an empty success", () => {
  assert.equal(parseDocument(null).meshes.length, 0);
  assert.throws(() => parseDocument({schema_version: 1, meshes: [{}]}));
});
