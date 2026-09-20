import * as THREE from "three";
import { LineSegments2 } from "three/addons/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/addons/lines/LineSegmentsGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import type { MeshPayload, Selection } from "../core/contracts.js";
import type { DisplayFrame } from "../core/math.js";
import { clippingPlane, displayPositions } from "../core/math.js";
import { pathSegments } from "../core/geometry.js";
import type { InspectionState } from "../core/state.js";
import { ResourceScope } from "./ResourceScope.js";

interface LineRecord { node: LineSegments2; scope: ResourceScope }
/** Batched diagnostic segments, not one Object3D per individual edge. */
export class DiagnosticLayer {
  readonly group = new THREE.Group();
  private readonly lines: LineRecord[] = [];
  private selected: LineRecord | null = null;
  private width = 1;
  private height = 1;
  private hasSelection = false;
  constructor(readonly mesh: MeshPayload, readonly frame: DisplayFrame) {
    try {
      for (const selection of mesh.selections) {
        const segments = this.selectionSegments(selection, false);
        if (segments.length) this.lines.push(this.line(segments, selection.id === "boundary" ? "#d1495b" : "#b76510", 2));
      }
      // At most five baseline path batches regardless of how many traces exist.
      const byStatus = new Map<string, number[]>();
      for (const path of mesh.paths) {
        const segments = byStatus.get(path.status) ?? [];
        for (const x of pathSegments(path.points)) segments.push(x);
        byStatus.set(path.status, segments);
      }
      for (const [status, segments] of byStatus) {
        this.lines.push(this.line(segments, status === "active" ? "#0284c7" : status === "cycle_detected" ? "#a855f7" : "#475569", 2.5));
      }
    } catch (error) { this.dispose(); throw error; }
  }
  selectionSegments(selection: Selection, includePaths = true): number[] {
    const segments = [...selection.segments];
    for (const index of selection.edge_pairs) {
      segments.push(this.mesh.positions[index * 3], this.mesh.positions[index * 3 + 1], this.mesh.positions[index * 3 + 2]);
    }
    if (includePaths) {
      const ids = new Set(selection.path_ids);
      for (const path of this.mesh.paths) if (ids.has(path.id)) for (const x of pathSegments(path.points)) segments.push(x);
    }
    return segments;
  }
  private line(segments: number[], color: string, linewidth: number): LineRecord {
    const scope = new ResourceScope();
    try {
      const geometry = scope.own(new LineSegmentsGeometry());
      geometry.setPositions(displayPositions(segments, this.frame));
      const material = scope.own(new LineMaterial({ color, linewidth, transparent: true, opacity: 0.9, depthWrite: false, toneMapped: false }));
      material.resolution.set(this.width, this.height);
      const node = new LineSegments2(geometry, material);
      node.renderOrder = 4; this.group.add(node);
      return { node, scope };
    } catch (error) { scope.dispose(); throw error; }
  }
  select(selection: Selection | null): void {
    this.hasSelection = selection !== null;
    if (this.selected) { this.selected.node.removeFromParent(); this.selected.scope.dispose(); this.selected = null; }
    if (selection) {
      const segments = this.selectionSegments(selection);
      if (segments.length) this.selected = this.line(segments, "#f97316", 4);
    }
  }
  update(state: InspectionState): void {
    const plane = clippingPlane(state.clipAxis, state.clipOffset, this.frame);
    const clipping = state.clipEnabled ? [new THREE.Plane(new THREE.Vector3(plane[0], plane[1], plane[2]), plane[3])] : [];
    for (const record of [...this.lines, ...(this.selected ? [this.selected] : [])]) {
      const material = record.node.material;
      const changed = (material.clippingPlanes?.length ?? 0) !== clipping.length;
      material.clippingPlanes = clipping;
      if (changed) material.needsUpdate = true;
      material.depthTest = !state.xray;
      record.node.visible = record === this.selected || !(state.isolate && this.hasSelection);
      material.opacity = record === this.selected ? 1 : this.hasSelection ? 0.25 : 0.85;
    }
  }
  pulse(opacity: number): void { if (this.selected) this.selected.node.material.opacity = opacity; }
  resize(width: number, height: number): void {
    this.width = width; this.height = height;
    for (const record of [...this.lines, ...(this.selected ? [this.selected] : [])]) record.node.material.resolution.set(width, height);
  }
  dispose(): void {
    this.group.removeFromParent(); this.group.clear();
    this.lines.forEach(line => line.scope.dispose()); this.lines.length = 0;
    this.selected?.scope.dispose(); this.selected = null;
  }
}
