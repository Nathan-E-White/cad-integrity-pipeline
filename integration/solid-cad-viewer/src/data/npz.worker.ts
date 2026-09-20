import { decodeNpz, type NpzOptions } from "./npz";
import type { NpzWorkerResponse } from "./NpzWorkerSource";
// Structural worker interface avoids mixing conflicting DOM and WebWorker lib declarations.
const worker = globalThis as unknown as {
  onmessage: ((event: MessageEvent<{ blob: Blob; options: NpzOptions }>) => void) | null;
  postMessage(value: NpzWorkerResponse, transfer?: Transferable[]): void;
};
worker.onmessage = async (event) => {
  try {
    const bytes = new Uint8Array(await event.data.blob.arrayBuffer());
    const document = await decodeNpz(bytes, event.data.options, new AbortController().signal);
    const buffers = new Set<ArrayBuffer>();
    for (const asset of document.geometries) {
      for (const array of [asset.positions, asset.indices, asset.normals, asset.uv, asset.triangleFaces, ...(asset.edges ?? []).map((edge) => edge.positions)]) {
        if (array?.buffer instanceof ArrayBuffer) buffers.add(array.buffer);
      }
    }
    worker.postMessage({ ok: true, document }, [...buffers]);
  } catch (error) {
    worker.postMessage({ ok: false, message: error instanceof Error ? error.message : String(error) });
  }
};
