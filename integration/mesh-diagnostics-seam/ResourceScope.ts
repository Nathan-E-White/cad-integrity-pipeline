export interface Disposable { dispose(): void }
/** Own resources explicitly, including resources shared by multiple scene nodes. */
export class ResourceScope {
  private readonly resources = new Set<Disposable>();
  private closed = false;
  own<T extends Disposable>(value: T): T {
    if (this.closed) { value.dispose(); throw new Error("Resource scope is closed"); }
    this.resources.add(value); return value;
  }
  dispose(): void {
    if (this.closed) return;
    this.closed = true;
    for (const resource of [...this.resources].reverse()) resource.dispose();
    this.resources.clear();
  }
}
