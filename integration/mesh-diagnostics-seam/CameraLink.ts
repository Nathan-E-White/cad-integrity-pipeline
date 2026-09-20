import type { Vec3 } from "../core/math.js";
export interface CameraPose { position: Vec3; target: Vec3; up: Vec3; fov: number; zoom: number; near: number; far: number }
export interface CameraPort { getPose(): CameraPose; setPose(pose: CameraPose): void; onPose: ((pose: CameraPose) => void) | null }
/** Bidirectional camera pose channel. Never copies aspect or assumes face correspondence. */
export function linkCameras(ports: readonly CameraPort[]): () => void {
  let applying = false;
  const old = ports.map(port => port.onPose);
  const handlers = ports.map((source, index) => (pose: CameraPose): void => {
    old[index]?.(pose);
    if (applying) return;
    applying = true;
    try { for (const target of ports) if (target !== source) target.setPose(pose); }
    finally { applying = false; }
  });
  ports.forEach((port, i) => { port.onPose = handlers[i]; });
  if (ports.length > 1) handlers[0](ports[0].getPose());
  return () => ports.forEach((port, i) => { if (port.onPose === handlers[i]) port.onPose = old[i]; });
}
