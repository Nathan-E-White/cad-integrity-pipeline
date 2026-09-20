/** On-demand frames, injectable clock hooks, idempotent teardown. */
export class FrameScheduler {
  private frame: number | null = null;
  private enabled = true;
  private disposed = false;
  private previous: number | null = null;
  constructor(private readonly tick: (seconds: number, delta: number) => boolean,
    private readonly request: (fn: FrameRequestCallback) => number = fn => requestAnimationFrame(fn),
    private readonly cancel: (id: number) => void = id => cancelAnimationFrame(id)) {}
  invalidate(): void {
    if (!this.disposed && this.enabled && this.frame === null) this.frame = this.request(this.step);
  }
  private step = (milliseconds: number): void => {
    this.frame = null;
    if (!this.enabled || this.disposed) return;
    const seconds = milliseconds / 1000;
    const delta = this.previous === null ? 1 / 60 : Math.min(0.1, Math.max(0, seconds - this.previous));
    this.previous = seconds;
    if (this.tick(seconds, delta)) this.invalidate();
  };
  setEnabled(value: boolean): void {
    this.enabled = value;
    if (!value) { if (this.frame !== null) this.cancel(this.frame); this.frame = null; this.previous = null; }
    else this.invalidate();
  }
  dispose(): void {
    if (this.disposed) return;
    this.setEnabled(false); this.disposed = true;
  }
}
