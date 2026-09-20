import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { deflateRawSync } from "node:zlib";
const require = createRequire(import.meta.url);
const { validateDocument, DEFAULT_MODEL_LIMITS } = require("../.core-build/src/model.js");
const { IDENTITY, multiply, transformPoint, worldTransforms, documentBounds, fitSphere } = require("../.core-build/src/math.js");
const { triangleSelection, isSelectionValid, selectedTriangleIndices } = require("../.core-build/src/selection.js");
const { readNpy, readNpz, decodeNpz, crc32, DEFAULT_ARCHIVE_LIMITS } = require("../.core-build/src/data/npz.js");
const { decodeDocument, encodeDocument } = require("../.core-build/src/data/wire.js");
const { HttpModelSource, NpzModelSource, StepModelSource, readResponseBytes } = require("../.core-build/src/data/sources.js");
const { makeDemoDocument } = require("../.core-build/src/demo/fixture.js");
const signal = () => new AbortController().signal;
function mesh() {
  return { schema: "cad-view/1", id: "test", revision: "1", name: "Test", units: "mm", upAxis: "Z",
    geometries: [{ id: "mesh", representation: "mesh", positions: new Float64Array([0, 0, 0, 2, 0, 0, 2, 1, 0, 0, 1, 0]),
      indices: new Uint32Array([0, 1, 2, 0, 2, 3]), faces: [{ id: "F42", kind: "brep-face" }], triangleFaces: new Int32Array([0, 0]) }],
    nodes: [{ id: "part", name: "Part", geometryId: "mesh" }] };
}
function npy(values, shape, { dtype = "<f8", version = 1, fortran = false } = {}) {
  const prefix = version === 1 ? 10 : 12;
  let header = `{'descr': '${dtype}', 'fortran_order': ${fortran ? "True" : "False"}, 'shape': (${shape.join(", ")}${shape.length === 1 ? "," : ""}), }`;
  header += " ".repeat((64 - (prefix + header.length + 1) % 64) % 64) + "\n";
  const width = Number(dtype.slice(2));
  const bytes = new Uint8Array(prefix + header.length + values.length * width);
  bytes.set([0x93, 78, 85, 77, 80, 89, version, 0]);
  const view = new DataView(bytes.buffer);
  if (version === 1) view.setUint16(8, header.length, true); else view.setUint32(8, header.length, true);
  bytes.set(new TextEncoder().encode(header), prefix);
  values.forEach((value, i) => {
    const p = prefix + header.length + i * width; const little = dtype[0] !== ">";
    if (dtype[1] === "f") { if (width === 8) view.setFloat64(p, value, little); else view.setFloat32(p, value, little); }
    else if (width === 8) { if (dtype[1] === "i") view.setBigInt64(p, BigInt(value), little); else view.setBigUint64(p, BigInt(value), little); }
    else if (dtype[1] === "i") { if (width === 4) view.setInt32(p, value, little); else if (width === 2) view.setInt16(p, value, little); else view.setInt8(p, value); }
    else { if (width === 4) view.setUint32(p, value, little); else if (width === 2) view.setUint16(p, value, little); else view.setUint8(p, value); }
  });
  return bytes;
}
function zip(entries, compressed = true) {
  const locals = []; const directory = []; let offset = 0;
  for (const [name, data] of entries) {
    const nameBytes = new TextEncoder().encode(name); const payload = compressed ? deflateRawSync(data) : data;
    const local = new Uint8Array(30 + nameBytes.length + payload.length); const l = new DataView(local.buffer);
    l.setUint32(0, 0x04034b50, true); l.setUint16(4, 20, true); l.setUint16(8, compressed ? 8 : 0, true);
    l.setUint32(14, crc32(data), true); l.setUint32(18, payload.length, true); l.setUint32(22, data.length, true); l.setUint16(26, nameBytes.length, true);
    local.set(nameBytes, 30); local.set(payload, 30 + nameBytes.length);
    const central = new Uint8Array(46 + nameBytes.length); const c = new DataView(central.buffer);
    c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(10, compressed ? 8 : 0, true);
    c.setUint32(16, crc32(data), true); c.setUint32(20, payload.length, true); c.setUint32(24, data.length, true); c.setUint16(28, nameBytes.length, true); c.setUint32(42, offset, true);
    central.set(nameBytes, 46); locals.push(local); directory.push(central); offset += local.length;
  }
  const size = directory.reduce((sum, bytes) => sum + bytes.length, 0);
  const end = new Uint8Array(22); const e = new DataView(end.buffer);
  e.setUint32(0, 0x06054b50, true); e.setUint16(8, entries.length, true); e.setUint16(10, entries.length, true); e.setUint32(12, size, true); e.setUint32(16, offset, true);
  return new Uint8Array(Buffer.concat([...locals, ...directory, end]));
}
function modelNpz(compressed = true) {
  return zip([["positions.npy", npy([0, 0, 0, 2, 0, 0, 0, 3, 0], [3, 3])], ["triangles.npy", npy([0, 1, 2], [1, 3], { dtype: "<i8" })],
    ["uv.npy", npy([0, 0, 4, 0, 0, 6], [3, 2])], ["triangle_faces.npy", npy([101], [1], { dtype: "<i4" })]], compressed);
}

test("accepts indexed mesh and topology-aware assembly fixture", () => { validateDocument(mesh()); validateDocument(makeDemoDocument()); });
test("rejects out-of-bounds triangle indices", () => { const d = mesh(); d.geometries[0].indices[0] = 40; assert.throws(() => validateDocument(d), /out-of-bounds/); });
test("rejects nonfinite positions", () => { const d = mesh(); d.geometries[0].positions[0] = NaN; assert.throws(() => validateDocument(d), /nonfinite/); });
test("rejects face-map count and range errors", () => { const d = mesh(); d.geometries[0].triangleFaces = new Int32Array([3, 0]); assert.throws(() => validateDocument(d), /face table/); d.geometries[0].triangleFaces = new Int32Array([0]); assert.throws(() => validateDocument(d), /triangle-face/); });
test("rejects duplicate IDs", () => { const d = mesh(); d.nodes.push({ ...d.nodes[0] }); assert.throws(() => validateDocument(d), /Duplicate node/); });
test("rejects cycles and missing parents", () => { const d = mesh(); d.nodes[0].parentId = "part"; assert.throws(() => validateDocument(d), /cycle/); d.nodes[0].parentId = "missing"; assert.throws(() => validateDocument(d), /Missing parent/); });
test("validates instance rendering budgets, not only unique asset size", () => { const d = mesh(); d.nodes.push({ id: "second", name: "Second", geometryId: "mesh" }); assert.throws(() => validateDocument(d, { ...DEFAULT_MODEL_LIMITS, maxDrawnTriangles: 3 }), /Instanced/); });
test("permits defective/degenerate triangles for inspection, without repairing", () => { const d = mesh(); d.geometries[0].indices.set([0, 0, 0]); validateDocument(d); assert.deepEqual([...d.geometries[0].indices.slice(0, 3)], [0, 0, 0]); });
test("rejects projective and singular transforms", () => { const d = mesh(); d.nodes[0].transform = [...IDENTITY]; d.nodes[0].transform[3] = 1; assert.throws(() => validateDocument(d), /projective/); d.nodes[0].transform = [...IDENTITY]; d.nodes[0].transform[0] = 0; assert.throws(() => validateDocument(d), /singular/); });
test("composes column-major matrices and preserves source units", () => { const t = [...IDENTITY]; t[12] = 10; const scale = [...IDENTITY]; scale[0] = 2; assert.deepEqual(transformPoint(multiply(t, scale), 3, 0, 0), [16, 0, 0]); });
test("resolves child-before-parent assemblies without recursion", () => { const d = mesh(); const t = [...IDENTITY]; t[12] = 100; d.nodes[0].parentId = "root"; d.nodes.push({ id: "root", name: "Root", transform: t }); validateDocument(d); assert.deepEqual(transformPoint(worldTransforms(d).get("part"), 0, 0, 0), [100, 0, 0]); });
test("handles a deeply nested hierarchy", () => { const d = mesh(); d.nodes = Array.from({ length: 15000 }, (_, i) => ({ id: String(i), name: String(i), parentId: i ? String(i - 1) : undefined })); validateDocument(d); assert.equal(worldTransforms(d).size, 15000); });
test("world bounds retain billion-unit offsets in double precision", () => { const d = makeDemoDocument(); const b = documentBounds(d); assert.ok(b.min[0] > 1e9 - 100); assert.ok(b.max[0] < 1e9 + 100); });
test("camera fit accounts for a narrow viewport", () => { assert.ok(fitSphere(1, 0.25, 45).distance > fitSphere(1, 2, 45).distance); assert.equal(fitSphere(1, 0.25, 45).orthoHalfHeight, 4.6); });
test("face picking returns semantic IDs rather than triangle IDs", () => { const d = mesh(); const s = triangleSelection(d, d.nodes[0], d.geometries[0], 1, "face"); assert.equal(s.kind, "face"); assert.equal(s.faceId, "F42"); assert.equal(selectedTriangleIndices(d.geometries[0], s).length, 6); });
test("unmapped faces fall back explicitly to triangle selection", () => { const d = mesh(); d.geometries[0].triangleFaces[1] = -1; assert.equal(triangleSelection(d, d.nodes[0], d.geometries[0], 1, "face").kind, "triangle"); });
test("selection identity includes instance and document revision", () => { const d = mesh(); const s = triangleSelection(d, d.nodes[0], d.geometries[0], 0, "face"); assert.equal(isSelectionValid(d, s), true); assert.equal(isSelectionValid({ ...d, revision: "2" }, s), false); assert.equal(isSelectionValid(d, { ...s, nodeId: "missing" }), false); });
test("JSON round trip preserves typed data, UVs, IDs and assembly transforms", () => { const d = makeDemoDocument(); const result = decodeDocument(JSON.parse(JSON.stringify(encodeDocument(d)))); assert.deepEqual(result.geometries[0].indices, d.geometries[0].indices); assert.equal(result.geometries[0].faces[0].id, "face-0"); assert.deepEqual(result.nodes[0].transform, d.nodes[0].transform); });
test("JSON decoding rejects fractional/negative indices before typed-array coercion", () => { const wire = encodeDocument(mesh()); wire.geometries[0].indices[0] = 0.5; assert.throws(() => decodeDocument(wire), /numeric/); wire.geometries[0].indices[0] = -1; assert.throws(() => decodeDocument(wire), /numeric/); });
for (const version of [1, 2, 3]) test(`reads NPY version ${version}`, () => { assert.deepEqual([...readNpy(npy([1.25, 2.5], [2], { version })).data], [1.25, 2.5]); });
test("reads big-endian float32 and signed int64", () => { assert.deepEqual([...readNpy(npy([1.25, 2.5], [2], { dtype: ">f4" })).data], [1.25, 2.5]); assert.deepEqual([...readNpy(npy([-3, 9], [2], { dtype: ">i8" })).data], [-3, 9]); });
test("converts Fortran-contiguous data to C-order without transposing logical coordinates", () => { assert.deepEqual([...readNpy(npy([0, 3, 1, 4, 2, 5], [2, 3], { fortran: true })).data], [0, 1, 2, 3, 4, 5]); });
test("converts rank-three Fortran storage", () => { assert.deepEqual([...readNpy(npy([0, 4, 2, 6, 1, 5, 3, 7], [2, 2, 2], { fortran: true })).data], [0, 1, 2, 3, 4, 5, 6, 7]); });
test("rejects unsafe 64-bit integer precision loss", () => { assert.throws(() => readNpy(npy([9007199254740993n], [1], { dtype: "<i8" })), /exact range/); });
test("rejects object/pickle dtypes", () => { const bytes = npy([1], [1]); const bad = new Uint8Array(bytes); const start = Buffer.from(bytes).indexOf("<f8"); bad.set(new TextEncoder().encode("|O8"), start); assert.throws(() => readNpy(bad), /no pickle/); });
test("rejects truncated NPY", () => { assert.throws(() => readNpy(npy([1, 2], [2]).slice(0, -1)), /payload/); });
for (const compressed of [false, true]) test(`reads ${compressed ? "deflated" : "stored"} NPZ with unnormalized UVs`, async () => { const d = await decodeNpz(modelNpz(compressed), { id: "npz", revision: "1", units: "mm" }, signal()); assert.deepEqual([...d.geometries[0].uv], [0, 0, 4, 0, 0, 6]); assert.equal(d.geometries[0].faces[0].id, "region:101"); assert.equal(d.geometries[0].faces[0].kind, "mesh-region"); });
test("reads a real numpy.savez_compressed artifact (local ZIP64 headers)", async () => { const bytes = readFileSync(new URL("../public/example.npz", import.meta.url)); const d = await decodeNpz(bytes, { id: "real-numpy", revision: "1", units: "mm" }, signal()); assert.equal(d.geometries[0].indices.length, 6); });
test("supports remapped NPZ keys", async () => { const bytes = zip([["V.npy", npy([0, 0, 0, 1, 0, 0, 0, 1, 0], [3, 3])], ["F.npy", npy([0, 1, 2], [1, 3])]]); const d = await decodeNpz(bytes, { id: "x", revision: "1", units: "unknown", keys: { positions: "V", triangles: "F" } }, signal()); assert.equal(d.units, "unknown"); });
test("rejects duplicate NPZ members", async () => { const bytes = zip([["x.npy", npy([1], [1])], ["x.npy", npy([2], [1])]]); await assert.rejects(() => readNpz(bytes, ["x"], signal()), /Duplicate/); });
test("rejects corrupt CRC", async () => { const bytes = zip([["x.npy", npy([1], [1])]], false); bytes[bytes.length - 1 - 22 - 46 - 5] ^= 1; await assert.rejects(() => readNpz(bytes, ["x"], signal()), /CRC/); });
test("enforces input and expanded ZIP budgets before decode", async () => { const bytes = modelNpz(); await assert.rejects(() => readNpz(bytes, ["positions"], signal(), { ...DEFAULT_ARCHIVE_LIMITS, maxInputBytes: 4 }), /size limit/); await assert.rejects(() => readNpz(bytes, ["positions"], signal(), { ...DEFAULT_ARCHIVE_LIMITS, maxExpandedBytes: 4 }), /expanded-size/); });
test("rejects an already cancelled NPZ load", async () => { const controller = new AbortController(); controller.abort(); await assert.rejects(() => readNpz(modelNpz(), ["positions"], controller.signal), { name: "AbortError" }); });
test("cancels in-progress decompression", async () => { const controller = new AbortController(); const pending = readNpz(modelNpz(), ["positions"], controller.signal); controller.abort(); await assert.rejects(() => pending, { name: "AbortError" }); });
test("checks CRC32 against known vector", () => { assert.equal(crc32(new TextEncoder().encode("123456789")), 0xcbf43926); });
test("HTTP source propagates AbortSignal and validates normalized data", async () => { const abortSignal = signal(); let received; const source = new HttpModelSource("/api/models/test", ["test", "1"], async (_url, init) => { received = init.signal; return new Response(JSON.stringify(encodeDocument(mesh()))); }); const d = await source.load(abortSignal); assert.equal(received, abortSignal); assert.equal(d.id, "test"); });
test("limits response bytes even without Content-Length", async () => { await assert.rejects(() => readResponseBytes(new Response("123456789"), signal(), 8), /too large/); });
test("HTTP failures remain explicit", async () => { const source = new HttpModelSource("/missing", ["missing"], async () => new Response("", { status: 404 })); await assert.rejects(() => source.load(signal()), /404/); });
test("Blob NPZ source is functional without a backend", async () => { const source = new NpzModelSource(new Blob([modelNpz()]), { id: "blob", revision: "2", units: "mm" }); assert.equal((await source.load(signal())).revision, "2"); });
test("STEP adapter validates output units and deflection, without pretending to parse STEP", async () => { const tessellator = { tessellate: async () => mesh() }; const source = new StepModelSource(["mock", "1"], new Blob(), tessellator, { outputUnits: "m", linearDeflection: 0.01, angularDeflectionRadians: 0.1 }); await assert.rejects(() => source.load(signal()), /unexpected units/); assert.throws(() => new StepModelSource(["mock"], new Blob(), tessellator, { outputUnits: "mm", linearDeflection: 0, angularDeflectionRadians: 0.1 }), /linear deflection/); });

const { createModelHandler } = require("../.core-build/src/server/model-handler.js");
test("model endpoint returns a validated exact revision", async () => {
  const handler = createModelHandler({ authorize: async () => true, load: async () => mesh() });
  const response = await handler(new Request("https://local.test/api/models/test?revision=1"));
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  assert.equal(decodeDocument(await response.json()).id, "test");
});
test("model endpoint authorizes before repository access", async () => {
  let loads = 0;
  const handler = createModelHandler({ authorize: async () => false, load: async () => { loads++; return mesh(); } });
  const response = await handler(new Request("https://local.test/api/models/test?revision=1"));
  assert.equal(response.status, 404); assert.equal(loads, 0);
});
test("model endpoint rejects wrong revisions without leaking diagnostics", async () => {
  const errors = [];
  const handler = createModelHandler({ authorize: async () => true, load: async () => mesh(), onError: (error) => errors.push(error) });
  const response = await handler(new Request("https://local.test/api/models/test?revision=2"));
  assert.equal(response.status, 500); assert.deepEqual(await response.json(), { error: "Model could not be loaded" });
  assert.equal(errors.length, 1);
});
test("model endpoint requires a revision and only handles GET", async () => {
  const handler = createModelHandler({ authorize: async () => true, load: async () => mesh() });
  assert.equal((await handler(new Request("https://local.test/api/models/test"))).status, 400);
  assert.equal((await handler(new Request("https://local.test/api/models/test?revision=1", { method: "POST" }))).status, 405);
});
