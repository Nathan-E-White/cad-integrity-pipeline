import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parsePayload, decodePayload } from "../src/model/parse.ts";
import { coordinateFrame, localPositions } from "../src/model/frame.ts";
import { trianglePositions, edgePositions } from "../src/model/buffers.ts";
import { ResourceScope } from "../src/render/resources.ts";

function fixture(): any {
  return JSON.parse(readFileSync(new URL("../demo/fixture.json", import.meta.url), "utf8"));
}

test("Python-generated fixture obeys the TypeScript contract", () => {
  const doc = parsePayload(fixture());
  assert.equal(doc.payload.schema_version, "mesh-diagnostics/1");
  assert.ok(doc.targets.size >= 4);
  assert.ok(doc.triangles instanceof Uint16Array);
});

test("null is a valid clear, malformed data is not a silent empty success", () => {
  assert.deepEqual(decodePayload(null), { document:null, error:null });
  assert.ok(decodePayload({}).error);
});

for (const bad of [-1, 0.5, Infinity, NaN, true, "0", 1e20]) {
  test(`reject bad index ${String(bad)} before unsigned conversion`, () => {
    const p = fixture(); p.triangles[0] = bad;
    assert.throws(() => parsePayload(p));
  });
}

test("reject stale targets", () => {
  const p = fixture(); p.targets[0].geometry_revision = "old";
  assert.throws(() => parsePayload(p), /different geometry revision/);
});

test("reject unknown metric targets and duplicate metric IDs", () => {
  const p = fixture(); p.metrics[0].target_id = "missing";
  assert.throws(() => parsePayload(p), /Unknown target/);
  const q = fixture(); q.metrics.push(q.metrics[0]);
  assert.throws(() => parsePayload(q), /Duplicate metric/);
});

test("large world origin is subtracted BEFORE float32 conversion", () => {
  const world = [1e12,1e12,1e12, 1e12+1,1e12,1e12];
  const frame = coordinateFrame(world);
  const local = localPositions(world,frame);
  assert.deepEqual([...local],[-1,0,0,1,0,0]);
  assert.equal(frame.scale,0.5);
});

test("extreme finite coordinates normalize without NaNs", () => {
  const world=[-1e308,0,0,1e308,0,0];
  assert.deepEqual([...localPositions(world,coordinateFrame(world))],[-1,0,0,1,0,0]);
});

test("empty or coincident geometry has a usable frame", () => {
  assert.equal(coordinateFrame([]).scale,1);
  assert.deepEqual([...localPositions([7,7,7],coordinateFrame([7,7,7]))],[0,0,0]);
});

test("face extraction preserves source triangle IDs", () => {
  const doc = parsePayload(fixture());
  const selected = trianglePositions(doc,[2]);
  for(let c=0;c<3;c++) {
    assert.deepEqual([...selected.slice(c*3,c*3+3)],
      [...doc.positions.slice(doc.triangles[6+c]*3,doc.triangles[6+c]*3+3)]);
  }
});

test("edge extraction uses source vertex indices", () => {
  const doc=parsePayload(fixture());
  const pos=edgePositions(doc,{id:"e",kind:"edges",geometry_revision:doc.payload.geometry_revision,indices:[0,1]});
  assert.deepEqual([...pos],[...doc.positions.slice(0,6)]);
});

test("uint32 is selected when the vertex table exceeds uint16 address space", () => {
  const p=fixture(); p.positions=new Array(65_537*3).fill(0);
  p.triangles=[0,1,65_536]; p.targets=[]; p.metrics=[];
  assert.ok(parsePayload(p).triangles instanceof Uint32Array);
});

test("resource ownership is idempotent and deduplicated", () => {
  const scope=new ResourceScope(); const order:string[]=[];
  const resource={dispose:()=>order.push("resource")};
  scope.own(resource); scope.own(resource); scope.defer(()=>order.push("callback"));
  scope.dispose(); scope.dispose();
  assert.deepEqual(order,["callback","resource"]);
  assert.throws(()=>scope.own({dispose(){}}),/disposed/);
});
