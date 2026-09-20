import { invariant, type ModelDocument } from "../model";
import type { NpzOptions } from "./npz";
import type { ModelSource } from "./sources";
export type NpzWorkerResponse = { ok: true; document: ModelDocument } | { ok: false; message: string };
/** Per-load worker ownership makes AbortSignal cancellation actually stop CPU decoding. */
export class NpzWorkerSource implements ModelSource {
  readonly cacheKey: readonly (string | number)[];
  constructor(private readonly blob: Blob, private readonly options: NpzOptions) {
    this.cacheKey = ["npz-worker", options.id, options.revision, options.units, options.upAxis ?? "Z", JSON.stringify(options.keys ?? {})];
  }
  load(signal: AbortSignal): Promise<ModelDocument> {
    signal.throwIfAborted();
    invariant(this.blob.size <= 64 * 1024 ** 2, "NPZ file exceeds the input budget");
    return new Promise((resolve, reject) => {
      const worker = new Worker(new URL("./npz.worker.ts", import.meta.url), { type: "module" });
      const finish = () => { worker.terminate(); signal.removeEventListener("abort", abort); };
      const abort = () => { finish(); reject(signal.reason ?? new DOMException("Aborted", "AbortError")); };
      signal.addEventListener("abort", abort, { once: true });
      worker.onmessage = (event: MessageEvent<NpzWorkerResponse>) => {
        finish();
        if (event.data.ok) resolve(event.data.document);
        else reject(new Error(event.data.message));
      };
      worker.onerror = (event) => { finish(); reject(new Error(event.message || "NPZ worker failed")); };
      worker.onmessageerror = () => { finish(); reject(new Error("Could not deserialize the NPZ worker result")); };
      if (signal.aborted) { abort(); return; }
      try { worker.postMessage({ blob: this.blob, options: this.options }); } catch (error) { finish(); reject(error); }
    });
  }
}
