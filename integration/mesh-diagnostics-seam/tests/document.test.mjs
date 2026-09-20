import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseDocument } from "../.core-build/core/contracts.js";
import { resolveTarget } from "../.core-build/core/selection.js";
import { frameFor, toDisplay, displayPositions, boundsFor } from "../.core-build/core/math.js";

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

const contractCases = JSON.parse(readFileSync(new URL("./contract-cases.json", import.meta.url)));
for (const scenario of contractCases) test(`shared wire contract: ${scenario.name}`, () => {
  const raw = structuredClone(fixture);
  raw.meshes = raw.meshes.slice(0, 1);
  const mesh = raw.meshes[0];
  mesh.triangle_source_faces = Array(mesh.triangles.length / 3).fill(0);
  let target = mesh;
  for (const key of scenario.path.slice(0, -1)) target = target[key];
  let value = "repeat" in scenario ? (scenario.text ?? "x").repeat(scenario.repeat) : scenario.value;
  if (scenario.path[0] === "triangle_source_faces") value = Array(mesh.triangles.length / 3).fill(value[0]);
  target[scenario.path.at(-1)] = value;
  if (scenario.accepted) assert.doesNotThrow(() => parseDocument(raw));
  else assert.throws(() => parseDocument(raw));
});

for (const kind of ["paths", "selections"]) test(`${kind} budget rejects before numeric validation`, () => {
  const raw = structuredClone(fixture);
  raw.meshes = raw.meshes.slice(0, 1);
  const coordinates = Array(kind === "paths" ? 750_003 : 31_254).fill(0);
  coordinates[0] = "invalid";
  raw.meshes[0][kind] = Array.from({length: kind === "paths" ? 2 : 256}, (_, i) =>
    kind === "paths" ? {id: `p${i}`, label: "Path", points: coordinates}
      : {id: `s${i}`, label: "Selection", segments: coordinates});
  assert.throws(() => parseDocument(raw), /budget exceeded/);
});

test("display fitting includes diagnostic segments on another carrier", () => {
  const raw = structuredClone(fixture);
  raw.meshes = raw.meshes.slice(0, 1);
  Object.assign(raw.meshes[0], {positions: [0,0,0, 2,0,0, 0,2,0], triangles: [0,1,2],
    fields: [], paths: [], metrics: [], selections: [{id:"edge", label:"External edge", segments:[10,0,0,12,0,0]}]});
  const mesh = parseDocument(raw).meshes[0];
  const frame = frameFor([mesh]);
  assert.deepEqual(frame.origin, [6,1,0]);
  assert.ok(Math.abs(frame.scale - Math.sqrt(37)) < 1e-14);
  assert.deepEqual(boundsFor([mesh]), {min:[0,0,0], max:[12,2,0]});
});

test("segment-only geometry at a distant origin remains renderable", () => {
  const raw = structuredClone(fixture);
  raw.meshes = raw.meshes.slice(0, 1);
  Object.assign(raw.meshes[0], {positions: [], triangles: [], fields: [], paths: [], metrics: [],
    selections: [{id:"edge", label:"External edge", segments:[1e40,0,0,1e40,2e40,0]}]});
  const mesh = parseDocument(raw).meshes[0];
  const frame = frameFor([mesh]);
  assert.deepEqual([...displayPositions(mesh.selections[0].segments, frame)], [0,-1,0,0,1,0]);
});
