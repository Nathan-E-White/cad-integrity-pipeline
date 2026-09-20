import { invariant, type LengthUnit, type ModelDocument, validateDocument } from "../model";

export interface NpyArray { readonly shape: readonly number[]; readonly data: Float64Array; readonly dtype: string; }
export interface ArchiveLimits { readonly maxInputBytes: number; readonly maxExpandedBytes: number; readonly maxEntries: number; readonly maxHeaderBytes: number; }
export const DEFAULT_ARCHIVE_LIMITS: ArchiveLimits = { maxInputBytes: 64 * 1024 ** 2, maxExpandedBytes: 192 * 1024 ** 2, maxEntries: 64, maxHeaderBytes: 64 * 1024 };

/** Numeric NPY v1/v2/v3 reader. Never evaluates Python or deserializes pickle. */
export function readNpy(bytes: Uint8Array, limits = DEFAULT_ARCHIVE_LIMITS): NpyArray {
  invariant(bytes.length >= 10 && bytes[0] === 0x93 && new TextDecoder().decode(bytes.subarray(1, 6)) === "NUMPY", "Not an NPY file");
  const major = bytes[6];
  invariant((major === 1 || major === 2 || major === 3) && bytes[7] === 0, "Unsupported NPY version");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const prefix = major === 1 ? 10 : 12;
  invariant(bytes.length >= prefix, "Truncated NPY prefix");
  const length = major === 1 ? view.getUint16(8, true) : view.getUint32(8, true);
  invariant(length <= limits.maxHeaderBytes && prefix + length <= bytes.length, "Invalid NPY header length");
  const header = new TextDecoder(major === 3 ? "utf-8" : "latin1", { fatal: true }).decode(bytes.subarray(prefix, prefix + length));
  // A deliberately restricted parser: structured, object, string, complex and datetime dtypes are rejected.
  const dtype = /['"]descr['"]\s*:\s*['"]([<>|=])([fiu])(1|2|4|8)['"]/.exec(header);
  const order = /['"]fortran_order['"]\s*:\s*(True|False)/.exec(header);
  const shapeMatch = /['"]shape['"]\s*:\s*\(([^)]*)\)/.exec(header);
  invariant(dtype && order && shapeMatch, "Unsupported NPY dtype/header (numeric arrays only; no pickle)");
  const shapeText = shapeMatch[1].trim();
  const parts = shapeText ? shapeText.split(",").map((part) => part.trim()).filter(Boolean) : [];
  invariant(parts.length <= 4 && parts.every((part) => /^\d+$/.test(part)), "Invalid NPY shape");
  const shape = parts.map(Number);
  let count = 1;
  for (const dimension of shape) {
    invariant(Number.isSafeInteger(dimension) && dimension >= 0, "Invalid NPY dimension");
    count *= dimension;
    invariant(Number.isSafeInteger(count) && count * 8 <= limits.maxExpandedBytes, "NPY element budget exceeded");
  }
  invariant(count * 8 <= limits.maxExpandedBytes, "NPY element budget exceeded");
  const width = Number(dtype[3]);
  const kind = dtype[2];
  invariant(kind !== "f" || width === 4 || width === 8, "Only float32/float64 are supported");
  invariant(dtype[1] !== "|" || width === 1, "Non-endian NPY dtype must be one byte");
  const nativeLittleEndian = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;
  const littleEndian = dtype[1] === "<" || (dtype[1] === "=" && nativeLittleEndian);
  const offset = prefix + length;
  invariant(count * width === bytes.length - offset, "NPY payload length does not match its shape");
  const result = new Float64Array(count);
  for (let i = 0; i < count; i++) {
    const p = offset + i * width;
    let value: number;
    if (kind === "f") value = width === 4 ? view.getFloat32(p, littleEndian) : view.getFloat64(p, littleEndian);
    else if (width === 8) {
      const integer = kind === "i" ? view.getBigInt64(p, littleEndian) : view.getBigUint64(p, littleEndian);
      invariant(integer >= BigInt(Number.MIN_SAFE_INTEGER) && integer <= BigInt(Number.MAX_SAFE_INTEGER), "Integer exceeds JavaScript's exact range");
      value = Number(integer);
    } else if (kind === "i") value = width === 1 ? view.getInt8(p) : width === 2 ? view.getInt16(p, littleEndian) : view.getInt32(p, littleEndian);
    else value = width === 1 ? view.getUint8(p) : width === 2 ? view.getUint16(p, littleEndian) : view.getUint32(p, littleEndian);
    result[i] = value;
  }
  if (order[1] === "False" || shape.length < 2) return { shape, data: result, dtype: dtype[0] };
  // Preserve logical indexing for Fortran-contiguous arrays; return C-order to the viewer.
  const cOrder = new Float64Array(count);
  for (let target = 0; target < count; target++) {
    let remainder = target;
    let source = 0;
    let stride = count;
    for (let axis = shape.length - 1; axis >= 0; axis--) {
      stride /= shape[axis];
      source += (remainder % shape[axis]) * stride;
      remainder = Math.floor(remainder / shape[axis]);
    }
    cOrder[target] = result[source];
  }
  return { shape, data: cOrder, dtype: dtype[0] };
}

const CRC_TABLE = Uint32Array.from({ length: 256 }, (_, i) => {
  let value = i;
  for (let k = 0; k < 8; k++) value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  return value >>> 0;
});
export function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = CRC_TABLE[(crc ^ byte) & 255] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

async function inflateBounded(input: Uint8Array, expected: number, signal: AbortSignal): Promise<Uint8Array> {
  signal.throwIfAborted();
  const stream = new Blob([new Uint8Array(input)]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  const reader = stream.getReader();
  const abort = () => { void reader.cancel(signal.reason).catch(() => undefined); };
  signal.addEventListener("abort", abort, { once: true });
  const output = new Uint8Array(expected);
  let offset = 0;
  try {
    while (true) {
      signal.throwIfAborted();
      const { done, value } = await reader.read();
      if (done) break;
      invariant(offset + value.byteLength <= expected, "ZIP decompression exceeded its declared length");
      output.set(value, offset); offset += value.byteLength;
    }
    signal.throwIfAborted();
    invariant(offset === expected, "Truncated ZIP member");
    return output;
  } finally {
    signal.removeEventListener("abort", abort);
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

/** ZIP/NPZ reader. Stored/deflated members only; central ZIP64/encryption/multi-disk rejected. */
export async function readNpz(bytes: Uint8Array, keys: readonly string[], signal: AbortSignal, limits = DEFAULT_ARCHIVE_LIMITS): Promise<ReadonlyMap<string, NpyArray>> {
  signal.throwIfAborted();
  invariant(bytes.byteLength <= limits.maxInputBytes && bytes.length >= 22, "NPZ input size limit exceeded or archive truncated");
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let end = -1;
  for (let p = bytes.length - 22; p >= Math.max(0, bytes.length - 65557); p--) {
    if (view.getUint32(p, true) === 0x06054b50 && p + 22 + view.getUint16(p + 20, true) === bytes.length) { end = p; break; }
  }
  invariant(end >= 0, "ZIP directory not found");
  const count = view.getUint16(end + 10, true);
  invariant(view.getUint16(end + 4, true) === 0 && view.getUint16(end + 6, true) === 0 && view.getUint16(end + 8, true) === count, "Multi-disk ZIP unsupported");
  invariant(count !== 0xffff && count <= limits.maxEntries, "ZIP entry budget exceeded / ZIP64 unsupported");
  const directorySize = view.getUint32(end + 12, true);
  const directoryStart = view.getUint32(end + 16, true);
  invariant(directoryStart + directorySize === end, "Malformed or unsupported ZIP directory");
  let cursor = directoryStart;
  let expanded = 0;
  const members: { key: string; start: number; compressed: number; size: number; method: number; crc: number }[] = [];
  const names = new Set<string>();
  const wanted = new Set(keys.map((key) => `${key}.npy`));
  for (let i = 0; i < count; i++) {
    invariant(cursor + 46 <= end && view.getUint32(cursor, true) === 0x02014b50, "Malformed ZIP central header");
    const flags = view.getUint16(cursor + 8, true);
    const method = view.getUint16(cursor + 10, true);
    const crc = view.getUint32(cursor + 16, true);
    const compressed = view.getUint32(cursor + 20, true);
    const size = view.getUint32(cursor + 24, true);
    const nameLength = view.getUint16(cursor + 28, true);
    const extraLength = view.getUint16(cursor + 30, true);
    const commentLength = view.getUint16(cursor + 32, true);
    const local = view.getUint32(cursor + 42, true);
    invariant((flags & 0x2041) === 0 && (method === 0 || method === 8), "Encrypted/unsupported ZIP compression");
    invariant(compressed !== 0xffffffff && size !== 0xffffffff && local !== 0xffffffff, "Central ZIP64 unsupported");
    invariant(cursor + 46 + nameLength + extraLength + commentLength <= end, "Truncated ZIP entry");
    const name = new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(cursor + 46, cursor + 46 + nameLength));
    invariant(!names.has(name), "Duplicate ZIP member"); names.add(name);
    expanded += size;
    invariant(expanded <= limits.maxExpandedBytes, "NPZ expanded-size budget exceeded");
    invariant(local + 30 <= directoryStart && view.getUint32(local, true) === 0x04034b50, "Invalid ZIP local header");
    invariant(view.getUint16(local + 8, true) === method && view.getUint16(local + 6, true) === flags, "ZIP header mismatch");
    const localNameLength = view.getUint16(local + 26, true);
    const start = local + 30 + localNameLength + view.getUint16(local + 28, true);
    invariant(start + compressed <= directoryStart, "ZIP member exceeds archive data");
    const localName = new TextDecoder().decode(bytes.subarray(local + 30, local + 30 + localNameLength));
    invariant(localName === name, "ZIP member name mismatch");
    if (wanted.has(name)) members.push({ key: name.slice(0, -4), start, compressed, size, method, crc });
    cursor += 46 + nameLength + extraLength + commentLength;
  }
  invariant(cursor === end, "ZIP directory length mismatch");
  const result = new Map<string, NpyArray>();
  let decodedBytes = 0;
  for (const member of members) {
    signal.throwIfAborted();
    const raw = bytes.subarray(member.start, member.start + member.compressed);
    const data = member.method === 0 ? raw : await inflateBounded(raw, member.size, signal);
    invariant(data.length === member.size && crc32(data) === member.crc, "NPZ CRC/size check failed");
    const array = readNpy(data, { ...limits, maxExpandedBytes: limits.maxExpandedBytes - decodedBytes });
    decodedBytes += array.data.byteLength;
    result.set(member.key, array);
    // Yield between arrays; for very large inputs use this module inside a worker.
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }
  signal.throwIfAborted();
  return result;
}

export interface NpzOptions {
  readonly id: string;
  readonly revision: string;
  readonly name?: string;
  readonly units: LengthUnit;
  readonly upAxis?: "Y" | "Z";
  readonly keys?: Partial<{ positions: string; triangles: string; normals: string; uv: string; triangleFaces: string }>;
}
/** NPZ has no universal mesh schema. This adapter explicitly declares one, with remappable keys. */
export async function decodeNpz(bytes: Uint8Array, options: NpzOptions, signal: AbortSignal): Promise<ModelDocument> {
  const keys = { positions: "positions", triangles: "triangles", normals: "normals", uv: "uv", triangleFaces: "triangle_faces", ...options.keys };
  const arrays = await readNpz(bytes, Object.values(keys), signal);
  const positions = arrays.get(keys.positions);
  const triangles = arrays.get(keys.triangles);
  invariant(positions && positions.shape.length === 2 && positions.shape[1] === 3, "positions must have shape (N,3)");
  invariant(triangles && triangles.shape.length === 2 && triangles.shape[1] === 3, "triangles must have shape (T,3)");
  for (const value of triangles.data) invariant(Number.isSafeInteger(value) && value >= 0 && value < positions.shape[0] && value <= 0xffffffff, "Invalid zero-based triangle index");
  const normals = arrays.get(keys.normals);
  const uv = arrays.get(keys.uv);
  invariant(!normals || (normals.shape.length === 2 && normals.shape[0] === positions.shape[0] && normals.shape[1] === 3), "normals must have shape (N,3)");
  invariant(!uv || (uv.shape.length === 2 && uv.shape[0] === positions.shape[0] && uv.shape[1] === 2), "uv must have shape (N,2)");
  const labels = arrays.get(keys.triangleFaces);
  invariant(!labels || (labels.shape.length === 1 && labels.shape[0] === triangles.shape[0]), "triangle_faces must have shape (T,)");
  const ids = new Map<number, number>();
  const triangleFaces = labels ? Int32Array.from(labels.data, (value) => {
    invariant(Number.isSafeInteger(value) && value >= -1, "Face labels must be integers >= -1");
    if (value === -1) return -1;
    if (!ids.has(value)) ids.set(value, ids.size);
    return ids.get(value) ?? -1;
  }) : undefined;
  const doc: ModelDocument = {
    schema: "cad-view/1", id: options.id, revision: options.revision, name: options.name ?? options.id,
    units: options.units, upAxis: options.upAxis ?? "Z",
    geometries: [{ id: "mesh", representation: "mesh", positions: positions.data,
      indices: Uint32Array.from(triangles.data), normals: normals ? Float32Array.from(normals.data) : undefined,
      uv: uv?.data, triangleFaces,
      // A numeric region tag is not evidence of an exact B-Rep face.
      faces: Array.from(ids.keys(), (id) => ({ id: `region:${id}`, kind: "mesh-region" as const })),
    }],
    nodes: [{ id: "part", name: options.name ?? options.id, geometryId: "mesh" }],
  };
  validateDocument(doc);
  return doc;
}
