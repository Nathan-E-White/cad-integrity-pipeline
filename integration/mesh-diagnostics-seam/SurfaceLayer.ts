import * as THREE from "three";
import type { MeshPayload, Selection } from "../core/contracts.js";
import type { DisplayFrame } from "../core/math.js";
import { clippingPlane } from "../core/math.js";
import { cornerBuffers } from "../core/geometry.js";
import { faceColors } from "../core/colors.js";
import type { InspectionState } from "../core/state.js";
import { ResourceScope } from "./ResourceScope.js";
import { surfaceVertex, surfaceFragment } from "./shaders.js";

export class SurfaceLayer {
  readonly group = new THREE.Group();
  readonly geometry: THREE.BufferGeometry;
  readonly center = new THREE.Vector3();
  readonly radius: number;
  readonly positions: Float32Array;
  readonly centers: Float32Array;
  private readonly scope = new ResourceScope();
  private readonly base: THREE.Mesh<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private readonly highlight: THREE.Mesh<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private readonly selectedAttribute: THREE.BufferAttribute;
  private readonly colorAttribute: THREE.BufferAttribute;
  private fieldId: string | null = null;
  private hasSelection = false;
  readonly selectedFaces = new Set<number>();

  constructor(readonly mesh: MeshPayload, readonly frame: DisplayFrame) {
    try {
    const buffers = cornerBuffers(mesh, frame);
    this.positions = buffers.positions; this.centers = buffers.centers;
    this.geometry = this.scope.own(new THREE.BufferGeometry());
    this.geometry.setAttribute("position", new THREE.BufferAttribute(buffers.positions, 3));
    this.geometry.setAttribute("aCenter", new THREE.BufferAttribute(buffers.centers, 3));
    this.geometry.setAttribute("aBarycentric", new THREE.BufferAttribute(buffers.barycentric, 3));
    this.colorAttribute = new THREE.BufferAttribute(new Float32Array(buffers.positions.length), 3).setUsage(THREE.DynamicDrawUsage);
    this.selectedAttribute = new THREE.BufferAttribute(new Float32Array(mesh.triangles.length), 1).setUsage(THREE.DynamicDrawUsage);
    this.geometry.setAttribute("aColor", this.colorAttribute);
    this.geometry.setAttribute("aSelected", this.selectedAttribute);
    if (buffers.positions.length) {
      this.geometry.computeBoundingSphere();
      const sphere = this.geometry.boundingSphere!;
      this.center.copy(sphere.center); this.radius = Math.max(sphere.radius, 1e-5);
    } else this.radius = 1;
    this.base = new THREE.Mesh(this.geometry, this.material(false));
    this.highlight = new THREE.Mesh(this.geometry, this.material(true));
    this.highlight.renderOrder = 3; this.highlight.visible = false;
    this.highlight.material.polygonOffset = true;
    this.highlight.material.polygonOffsetFactor = -2;
    this.highlight.material.polygonOffsetUnits = -2;
    this.base.renderOrder = 1;
    this.group.add(this.base, this.highlight);
    } catch (error) { this.scope.dispose(); throw error; }
  }

  private material(selectionPass: boolean): THREE.ShaderMaterial {
    return this.scope.own(new THREE.ShaderMaterial({ vertexShader: surfaceVertex, fragmentShader: surfaceFragment,
      side: THREE.DoubleSide, transparent: selectionPass, depthWrite: !selectionPass, toneMapped: false,
      uniforms: {
        uShrink: { value: 1 }, uClip: { value: false }, uPlane: { value: new THREE.Vector4(-1, 0, 0, 0) },
        uPeel: { value: false }, uPeelCenter: { value: this.center.clone() }, uPeelRadius: { value: this.radius },
        uHeatmap: { value: false }, uWire: { value: true }, uWireOnly: { value: false },
        uSelectionPass: { value: selectionPass }, uIsolate: { value: false }, uOpacity: { value: 1 },
        uSurfaceColor: { value: new THREE.Color("#64748b") }, uWireColor: { value: new THREE.Color("#172b40") },
        uSelectedColor: { value: new THREE.Color("#f97316") },
      },
    }));
  }

  select(selection: Selection | null): void {
    this.hasSelection = selection !== null;
    this.selectedFaces.clear();
    (this.selectedAttribute.array as Float32Array).fill(0);
    for (const id of selection?.face_ids ?? []) {
      this.selectedFaces.add(id);
      (this.selectedAttribute.array as Float32Array).fill(1, id * 3, id * 3 + 3);
    }
    this.selectedAttribute.needsUpdate = true;
    this.highlight.visible = this.selectedFaces.size > 0;
  }

  update(state: InspectionState): void {
    const field = this.mesh.fields.find(f => f.id === state.fieldId);
    const fieldId = field?.id ?? null;
    if (fieldId !== this.fieldId) {
      if (field) (this.colorAttribute.array as Float32Array).set(faceColors(field.values, field.domain));
      this.colorAttribute.needsUpdate = true; this.fieldId = fieldId;
    }
    const plane = clippingPlane(state.clipAxis, state.clipOffset, this.frame);
    for (const material of [this.base.material, this.highlight.material]) {
      const u = material.uniforms;
      u.uShrink.value = state.shrink;
      u.uClip.value = state.clipEnabled; (u.uPlane.value as THREE.Vector4).fromArray(plane);
      u.uPeel.value = state.peelEnabled; u.uPeelRadius.value = this.radius * state.radialFraction;
      u.uHeatmap.value = field !== undefined;
      u.uWire.value = state.wire; u.uWireOnly.value = state.mode === "wireframe";
      u.uIsolate.value = state.isolate && this.hasSelection;
    }
    const ghost = state.mode === "ghost" || (this.hasSelection && !state.isolate);
    this.base.material.uniforms.uOpacity.value = ghost ? 0.20 : 1;
    const transparent = ghost || state.mode === "wireframe";
    if (this.base.material.transparent !== transparent) this.base.material.needsUpdate = true;
    this.base.material.transparent = transparent;
    this.base.material.depthWrite = !transparent;
    this.highlight.material.depthTest = !state.xray;
  }
  pulse(opacity: number): void { this.highlight.material.uniforms.uOpacity.value = opacity; }
  dispose(): void { this.group.removeFromParent(); this.group.clear(); this.scope.dispose(); }
}
