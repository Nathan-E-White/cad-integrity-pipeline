import { test, expect } from 'bun:test';
import { decodeInspectionWire } from '../src/core/wire';
test('raw documents and empty values pass through without transport work', async () => {
    const text = JSON.stringify({ schema_version: 2, meshes: [] });
    expect(await decodeInspectionWire(text)).toBe(text);
    expect(await decodeInspectionWire(null)).toBe(null);
});
test('managed file delivery inflates once and enforces the same document budget', async () => {
    const text = JSON.stringify({ schema_version: 2, meshes: [] });
    const url = 'data:application/gzip;base64,' + Buffer.from(Bun.gzipSync(text)).toString('base64');
    expect(await decodeInspectionWire({ url })).toBe(text);
    expect(decodeInspectionWire({ url }, 10)).rejects.toThrow('limit');
    expect(decodeInspectionWire({ url: 42 })).rejects.toThrow('URL');
});
test('transport unavailability is explicit and empty delivery clears the workspace', async () => {
    expect(await decodeInspectionWire({ file: null, error: null })).toBe(null);
    expect(decodeInspectionWire({ file: null, error: 'cache unavailable' })).rejects.toThrow('cache unavailable');
});
test('superseded transport fetches are cancelled', async () => {
    const controller = new AbortController();
    controller.abort();
    expect(decodeInspectionWire({ url: 'data:application/gzip;base64,' + Buffer.from(Bun.gzipSync('{}')).toString('base64') }, 1024, controller.signal)).rejects.toThrow();
});
