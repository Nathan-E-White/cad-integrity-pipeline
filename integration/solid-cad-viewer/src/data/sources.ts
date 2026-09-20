import { invariant, type ModelDocument, validateDocument } from "../model";
import { decodeNpz, type NpzOptions } from "./npz";
import { decodeDocument } from "./wire";

export interface ModelSource {
  /** Include source namespace, authorization scope, revision and tessellation options. No credentials. */
  readonly cacheKey: readonly (string | number)[];
  load(signal: AbortSignal): Promise<ModelDocument>;
}
export async function readResponseBytes(response: Response, signal: AbortSignal, maxBytes = 64 * 1024 ** 2): Promise<Uint8Array> {
  if (!response.ok) throw new Error(`Model request failed: HTTP ${response.status}`);
  const claimed = Number(response.headers.get("content-length"));
  invariant(!Number.isFinite(claimed) || claimed <= maxBytes, "Response too large");
  invariant(response.body, "Empty response body");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  const abort = () => { void reader.cancel(signal.reason).catch(() => undefined); };
  signal.addEventListener("abort", abort, { once: true });
  try {
    while (true) {
      signal.throwIfAborted();
      const next = await reader.read();
      if (next.done) break;
      length += next.value.length;
      invariant(length <= maxBytes, "Response too large");
      chunks.push(next.value);
    }
    signal.throwIfAborted();
  } finally {
    signal.removeEventListener("abort", abort);
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
  const result = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
  return result;
}

export class HttpModelSource implements ModelSource {
  constructor(readonly url: string, readonly cacheKey: readonly (string | number)[], private readonly fetcher: typeof fetch = fetch) {}
  async load(signal: AbortSignal): Promise<ModelDocument> {
    const response = await this.fetcher(this.url, { signal, credentials: "same-origin", headers: { accept: "application/json" } });
    const bytes = await readResponseBytes(response, signal);
    signal.throwIfAborted();
    return decodeDocument(JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)));
  }
}
export class NpzModelSource implements ModelSource {
  readonly cacheKey: readonly (string | number)[];
  constructor(private readonly blob: Blob, private readonly options: NpzOptions) {
    this.cacheKey = ["npz", options.id, options.revision, options.units, options.upAxis ?? "Z", JSON.stringify(options.keys ?? {})];
  }
  async load(signal: AbortSignal): Promise<ModelDocument> {
    signal.throwIfAborted();
    invariant(this.blob.size <= 64 * 1024 ** 2, "NPZ file exceeds the input budget");
    const buffer = await this.blob.arrayBuffer();
    signal.throwIfAborted();
    return decodeNpz(new Uint8Array(buffer), this.options, signal);
  }
}

export interface TessellationOptions {
  /** In OUTPUT document units; strictly positive. */
  readonly linearDeflection: number;
  readonly angularDeflectionRadians: number;
  readonly outputUnits: ModelDocument["units"];
}
export interface StepTessellator {
  /** Must return face-oriented triangles plus retained semantic IDs; apply CAD locations and units. */
  tessellate(step: Blob, options: TessellationOptions, signal: AbortSignal): Promise<ModelDocument>;
}
/** Injection boundary: a server service or a worker-backed OpenCascade adapter belongs here. */
export class StepModelSource implements ModelSource {
  constructor(readonly cacheKey: readonly (string | number)[], private readonly blob: Blob, private readonly tessellator: StepTessellator, private readonly options: TessellationOptions) {
    invariant(Number.isFinite(options.linearDeflection) && options.linearDeflection > 0, "Invalid linear deflection");
    invariant(Number.isFinite(options.angularDeflectionRadians) && options.angularDeflectionRadians > 0 && options.angularDeflectionRadians < Math.PI, "Invalid angular deflection");
  }
  async load(signal: AbortSignal): Promise<ModelDocument> {
    signal.throwIfAborted();
    const result = await this.tessellator.tessellate(this.blob, this.options, signal);
    signal.throwIfAborted();
    validateDocument(result);
    invariant(result.units === this.options.outputUnits, "Tessellator returned unexpected units");
    return result;
  }
}
