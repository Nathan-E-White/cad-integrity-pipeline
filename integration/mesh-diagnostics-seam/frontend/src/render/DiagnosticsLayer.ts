import * as THREE from "three";
import { LineSegments2 } from "three/addons/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/addons/lines/LineSegmentsGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import type { MeshDocument, Target } from "../model/types.ts";
import { edgePositions, triangleEdgePositions, trianglePositions } from "../model/buffers.ts";
import { ResourceScope } from "./resources.ts";

interface Overlay {
  baseColor: number;
  group: THREE.Group;
  materials: THREE.Material[];
  scope: ResourceScope;
}
function colorFor(doc: MeshDocument, id: string): number {
  const statuses = doc.payload.metrics.filter((m) => m.target_id === id).map((m) => m.status);
  if (statuses.includes("fail")) return 0xf43f5e;
  if (statuses.includes("warn")) return 0xf97316;
  return 0x0891b2;
}
function addLines(overlay: Overlay, positions: Float32Array, color: number, width = 3): void {
  const geometry = overlay.scope.own(new LineSegmentsGeometry());
  geometry.setPositions(positions);
  const material = overlay.scope.own(new LineMaterial({
    color, linewidth: width, worldUnits: false, transparent: true,
    opacity: 0.9, depthWrite: false, alphaToCoverage: true,
  }));
  const lines = new LineSegments2(geometry, material);
  lines.renderOrder = 20;
  overlay.materials.push(material);
  overlay.group.add(lines);
}
function makeOverlay(doc: MeshDocument, target: Target): Overlay {
  const overlay: Overlay = { baseColor: colorFor(doc, target.id), group: new THREE.Group(), materials: [], scope: new ResourceScope() };
  try {
    const color = colorFor(doc, target.id);
    if (target.kind !== "faces") {
      if ((target.kind === "edges" ? target.indices.length : target.positions.length) > 0) {
        addLines(overlay, edgePositions(doc, target), color);
      }
    } else if (target.ids.length) {
      // A compact selection, not another full copy of the source vertex buffer.
      const positions = trianglePositions(doc, target.ids);
      const geometry = overlay.scope.own(new THREE.BufferGeometry());
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      const material = overlay.scope.own(new THREE.MeshBasicMaterial({
        color: 0xf97316, side: THREE.DoubleSide, transparent: true,
        opacity: 0.8, depthWrite: false, polygonOffset: true,
        polygonOffsetFactor: -1, polygonOffsetUnits: -2,
      }));
      material.forceSinglePass = true;
      const mesh = new THREE.Mesh(geometry, material);
      mesh.renderOrder = 20;
      overlay.group.add(mesh);
      overlay.materials.push(material);
      addLines(overlay, triangleEdgePositions(positions), 0xf97316, 2);
      // Points make even zero-area and fully collapsed triangles discoverable.
      const pointsMaterial = overlay.scope.own(new THREE.PointsMaterial({
        color: 0xf97316, size: 5, sizeAttenuation: false, transparent: true, depthWrite: false,
      }));
      // Geometry is shared INSIDE one ownership scope and disposed exactly once.
      const points = new THREE.Points(geometry, pointsMaterial);
      points.renderOrder = 21;
      overlay.materials.push(pointsMaterial);
      overlay.group.add(points);
    }
    return overlay;
  } catch (error) { overlay.scope.dispose(); throw error; }
}

/** Framework-independent overlay layer. Map this seam onto ViewerLayer.mount(context). */
export class DiagnosticsLayer {
  readonly group = new THREE.Group();
  private doc: MeshDocument;
  private edges = new Map<string, Overlay>();
  private selectedFaces: { id: string; overlay: Overlay } | null = null;
  private selected: string | null = null;
  private xray = true;
  private disposed = false;

  constructor(doc: MeshDocument) {
    this.doc = doc;
    try {
      // One batched line object per target/category, not per mesh edge.
      for (const target of doc.targets.values()) {
        if (target.kind === "faces") continue;
        const overlay = makeOverlay(doc, target);
        this.edges.set(target.id, overlay);
        this.group.add(overlay.group);
      }
      this.applyStyle(1);
    } catch (error) { this.dispose(); throw error; }
  }
  setSelection(id: string | null): void {
    if (id === this.selected || this.disposed) return;
    this.selected = id;
    if (this.selectedFaces && this.selectedFaces.id !== id) {
      this.group.remove(this.selectedFaces.overlay.group);
      this.selectedFaces.overlay.scope.dispose();
      this.selectedFaces = null;
    }
    const target = id ? this.doc.targets.get(id) : undefined;
    if (target?.kind === "faces" && !this.selectedFaces) {
      const overlay = makeOverlay(this.doc, target);
      this.selectedFaces = { id: target.id, overlay };
      this.group.add(overlay.group);
    }
    this.applyStyle(1);
  }
  setXray(enabled: boolean): void { this.xray = enabled; this.applyStyle(1); }
  setPulse(opacity: number): void { this.applyStyle(opacity); }
  private applyStyle(pulse: number): void {
    const style = (overlay: Overlay, selected: boolean) => {
      overlay.group.visible = true;
      for (const material of overlay.materials) {
        material.depthTest = !this.xray;
        const colored = material as THREE.Material & { color?: THREE.Color };
        colored.color?.set(selected ? 0xf97316 : overlay.baseColor);
        material.opacity = selected ? 0.8 * pulse : (this.selected ? 0.12 : 0.85);
      }
    };
    for (const [id, overlay] of this.edges) style(overlay, id === this.selected);
    if (this.selectedFaces) style(this.selectedFaces.overlay, true);
  }
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    for (const overlay of this.edges.values()) overlay.scope.dispose();
    this.edges.clear();
    this.selectedFaces?.overlay.scope.dispose();
    this.selectedFaces = null;
    this.group.clear();
    this.group.removeFromParent();
  }
}
