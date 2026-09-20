/** Keep Gradio's event stream bounded; geometry remains lossless and browser-local. */
export async function decodeInspectionWire(value: unknown, limit = 512 * 1024 ** 2, signal?: AbortSignal): Promise<unknown> {
    if (value && typeof value === 'object' && 'file' in value) {
        const delivery = value as {
            file: unknown;
            error?: unknown;
        };
        if (typeof delivery.error === 'string')
            throw new Error(delivery.error);
        return decodeInspectionWire(delivery.file, limit, signal);
    }
    if (value && typeof value === 'object' && 'url' in value) {
        const url = (value as {
            url: unknown;
        }).url;
        if (typeof url !== 'string')
            throw new Error('Invalid inspection transport URL');
        const response = await fetch(url, { signal });
        if (!response.ok || !response.body)
            throw new Error('Inspection delivery unavailable');
        return inflate(response.body, limit, signal);
    }
    return value;
}
async function inflate(stream: ReadableStream<Uint8Array<ArrayBuffer>>, limit: number, signal?: AbortSignal): Promise<string> {
    const reader = stream.pipeThrough(new DecompressionStream('gzip')).getReader();
    const abort = () => { reader.cancel().catch(() => { }); };
    signal?.addEventListener('abort', abort, { once: true });
    const decoder = new TextDecoder('utf-8', { fatal: true });
    const chunks: string[] = [];
    let size = 0;
    try {
        signal?.throwIfAborted();
        while (true) {
            const chunk = await reader.read();
            if (chunk.done)
                break;
            size += chunk.value.byteLength;
            if (size > limit)
                throw new Error('Inspection document exceeds limit');
            chunks.push(decoder.decode(chunk.value, { stream: true }));
        }
        signal?.throwIfAborted();
        chunks.push(decoder.decode());
        return chunks.join('');
    }
    finally {
        signal?.removeEventListener('abort', abort);
        await reader.cancel();
    }
}
