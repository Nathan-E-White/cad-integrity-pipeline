import { invariant, type ModelDocument } from "../model";
import { encodeDocument } from "../data/wire";

export interface ModelRequest {
  readonly request: Request;
  readonly id: string;
  readonly revision: string;
  readonly signal: AbortSignal;
}
export interface ModelService {
  /** Mandatory policy decision; authenticate and authorize before accessing model storage. */
  authorize(context: ModelRequest): Promise<boolean>;
  /** Resolve opaque IDs through a repository. Do not treat IDs as paths or remote URLs. */
  load(context: ModelRequest): Promise<ModelDocument | null>;
  /** Server-only diagnostics. Raw exceptions are never returned to the client. */
  onError?(error: unknown): void;
}

function json(value: unknown, status = 200, extraHeaders: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "private, no-store",
      "x-content-type-options": "nosniff",
      ...extraHeaders,
    },
  });
}

/** Framework-independent Web Request/Response handler; see examples/nitro for its thin wrapper. */
export function createModelHandler(service: ModelService): (request: Request) => Promise<Response> {
  return async (request) => {
    if (request.method !== "GET") return json({ error: "Method not allowed" }, 405, { allow: "GET" });
    const url = new URL(request.url);
    const match = /^\/api\/models\/([A-Za-z0-9][A-Za-z0-9._-]{0,127})\/?$/.exec(url.pathname);
    if (!match) return json({ error: "Not found" }, 404);
    const revision = url.searchParams.get("revision");
    if (!revision || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(revision)) {
      return json({ error: "A valid revision is required" }, 400);
    }
    const context: ModelRequest = { request, id: match[1], revision, signal: request.signal };
    try {
      request.signal.throwIfAborted();
      // Identical denial/not-found responses avoid revealing model existence to an unauthorized caller.
      if (!(await service.authorize(context))) return json({ error: "Not found" }, 404);
      request.signal.throwIfAborted();
      const document = await service.load(context);
      request.signal.throwIfAborted();
      if (!document) return json({ error: "Not found" }, 404);
      invariant(document.id === context.id && document.revision === revision, "Repository returned the wrong model revision");
      return json(encodeDocument(document));
    } catch (error) {
      if (request.signal.aborted) throw error;
      service.onError?.(error);
      return json({ error: "Model could not be loaded" }, 500);
    }
  };
}
