export interface Disposable { dispose(): void }
/** Explicit ownership. Never discover/dispose shared GPU resources by scene traversal. */
export class ResourceScope implements Disposable {
  private callbacks: (() => void)[] = [];
  private resources = new Set<Disposable>();
  private disposed = false;
  own<T extends Disposable>(resource: T): T {
    if (this.disposed) throw new Error("ResourceScope is disposed");
    if (!this.resources.has(resource)) {
      this.resources.add(resource);
      this.callbacks.push(() => resource.dispose());
    }
    return resource;
  }
  defer(cleanup: () => void): void {
    if (this.disposed) throw new Error("ResourceScope is disposed");
    this.callbacks.push(cleanup);
  }
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    const errors: unknown[] = [];
    for (const cleanup of this.callbacks.reverse()) {
      try { cleanup(); } catch (error) { errors.push(error); }
    }
    this.callbacks = [];
    this.resources.clear();
    if (errors.length) console.error("Resource cleanup errors", errors);
  }
}
