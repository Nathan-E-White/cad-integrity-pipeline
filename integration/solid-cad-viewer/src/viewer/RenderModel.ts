import * as THREE from "three";
import { boundsOf, centerOf, documentBounds, IDENTITY, worldTransforms } from "../math";
import { type GeometryAsset, invariant, type ModelDocument, type ModelNode, type Selection, type Vec3, validateDocument } from "../model";
import { isSelectionValid, selectedTriangleIndices } from "../selection";
import type { ViewerTheme } from "./theme";

export type DisplayMode = "shaded" | "shaded-edges" | "wireframe";
interface RenderAsset {
  source: GeometryAsset;
  center: Vec3;
  triangles: THREE.BufferGeometry;
  edges: THREE.BufferGeometry;
  /** Absent for inferred visual feature edges: those are not CAD topology. */
  segmentToEdge?: Uint32Array;
}
export interface RenderInstance {
  node: ModelNode;
  asset: RenderAsset;
  group: THREE.Group;
  surface: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;
  edges: THREE.LineSegments<THREE.BufferGeometry, THREE.LineBasicMaterial>;
}
function centeredPositions(values: ArrayLike<number>, center: Vec3): Float32Array {
  const result = new Float32Array(values.length);
  for (let i = 0; i < values.length; i++) {
    result[i] = values[i] - center[i % 3];
    invariant(Number.isFinite(result[i]), "Coordinate cannot be represented in GPU float32");
  }
  return result;
}

/** Owns its GPU resources. The input document and its buffers remain caller-owned. */
export class RenderModel {
  readonly root = new THREE.Group();
  readonly instances = new Map<string, RenderInstance>();
  readonly origin: Vec3;
  private readonly geometries = new Set<THREE.BufferGeometry>();
  private readonly materials = new Set<THREE.Material>();
  private readonly nodes: ReadonlyMap<string, ModelNode>;
  private readonly visibility = new Map<string, boolean>();
  private highlight?: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial> | THREE.LineSegments<THREE.BufferGeometry, THREE.LineBasicMaterial>;
  private planes: THREE.Plane[] = [];
  private mode: DisplayMode = "shaded-edges";
  private disposed = false;

  private constructor(readonly document: ModelDocument, private readonly theme: ViewerTheme) {
    this.nodes = new Map(document.nodes.map((node) => [node.id, node]));
    this.origin = centerOf(documentBounds(document));
  }
  /** Build first, swap second: invalid geometry never destroys the currently displayed model. */
  static create(document: ModelDocument, theme: ViewerTheme): RenderModel {
    validateDocument(document);
    const model = new RenderModel(document, theme);
    try { model.build(); return model; } catch (error) { model.dispose(); throw error; }
  }
  private ownGeometry(geometry: THREE.BufferGeometry): THREE.BufferGeometry {
    this.geometries.add(geometry); return geometry;
  }
  private makeAsset(source: GeometryAsset): RenderAsset {
    let localBounds = boundsOf(source.positions);
    for (const edge of source.edges ?? []) {
      const b = boundsOf(edge.positions);
      if (b) localBounds = localBounds ? {
        min: localBounds.min.map((v, i) => Math.min(v, b.min[i])) as unknown as Vec3,
        max: localBounds.max.map((v, i) => Math.max(v, b.max[i])) as unknown as Vec3,
      } : b;
    }
    const center = centerOf(localBounds);
    const triangles = this.ownGeometry(new THREE.BufferGeometry());
    triangles.setAttribute("position", new THREE.BufferAttribute(centeredPositions(source.positions, center), 3));
    triangles.setIndex(new THREE.BufferAttribute(source.indices.slice(), 1));
    if (source.normals) triangles.setAttribute("normal", new THREE.BufferAttribute(source.normals.slice(), 3));
    else if (source.indices.length) triangles.computeVertexNormals();
    if (source.uv) triangles.setAttribute("uv", new THREE.BufferAttribute(Float32Array.from(source.uv), 2));
    triangles.computeBoundingBox(); triangles.computeBoundingSphere();
    if (!source.edges?.length) {
      const edges = this.ownGeometry(source.indices.length ? new THREE.EdgesGeometry(triangles, 35) : new THREE.BufferGeometry());
      return { source, center, triangles, edges };
    }
    const segmentCount = source.edges.reduce((sum, edge) => sum + edge.positions.length / 3 - 1, 0);
    const segments = new Float32Array(segmentCount * 6);
    const segmentToEdge = new Uint32Array(segmentCount);
    let segment = 0;
    for (let edgeIndex = 0; edgeIndex < source.edges.length; edgeIndex++) {
      const points = source.edges[edgeIndex].positions;
      for (let p = 0; p < points.length - 3; p += 3) {
        for (let j = 0; j < 6; j++) segments[segment * 6 + j] = points[p + j] - center[j % 3];
        segmentToEdge[segment++] = edgeIndex;
      }
    }
    for (const v of segments) invariant(Number.isFinite(v), "Edge coordinate overflow");
    const edges = this.ownGeometry(new THREE.BufferGeometry());
    edges.setAttribute("position", new THREE.BufferAttribute(segments, 3));
    edges.computeBoundingBox(); edges.computeBoundingSphere();
    return { source, center, triangles, edges, segmentToEdge };
  }
  private build(): void {
    const assets = new Map(this.document.geometries.map((source) => [source.id, this.makeAsset(source)]));
    const transforms = worldTransforms(this.document);
    for (const node of this.document.nodes) {
      this.visibility.set(node.id, node.visible !== false);
      const asset = node.geometryId === undefined ? undefined : assets.get(node.geometryId);
      if (!asset) continue;
      const group = new THREE.Group(); group.name = node.name;
      group.matrixAutoUpdate = false;
      group.matrix.fromArray(transforms.get(node.id) ?? IDENTITY);
      group.matrix.multiply(new THREE.Matrix4().makeTranslation(...asset.center));
      // Cancel large translations in JS double precision BEFORE the matrix reaches WebGL.
      group.matrix.elements[12] -= this.origin[0];
      group.matrix.elements[13] -= this.origin[1];
      group.matrix.elements[14] -= this.origin[2];
      invariant(group.matrix.elements.every((value) => Number.isFinite(Math.fround(value))), "World matrix overflow");
      const material = new THREE.MeshStandardMaterial({ color: asset.source.color ?? this.theme.surface,
        metalness: 0.08, roughness: 0.67, side: THREE.DoubleSide,
        flatShading: !asset.source.normals, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
      const lineMaterial = new THREE.LineBasicMaterial({ color: this.theme.edge });
      this.materials.add(material); this.materials.add(lineMaterial);
      const surface = new THREE.Mesh(asset.triangles, material);
      const edges = new THREE.LineSegments(asset.edges, lineMaterial);
      edges.renderOrder = 1;
      group.add(surface, edges); this.root.add(group);
      this.instances.set(node.id, { node, asset, group, surface, edges });
    }
    this.refreshVisibility();
    this.setDisplayMode(this.mode);
    this.root.updateMatrixWorld(true);
  }
  setDisplayMode(mode: DisplayMode): void {
    this.mode = mode;
    for (const instance of this.instances.values()) {
      instance.surface.material.wireframe = mode === "wireframe";
      instance.edges.visible = mode === "shaded-edges";
    }
  }
  get displayMode(): DisplayMode { return this.mode; }
  setVisible(id: string, visible: boolean): void {
    invariant(this.nodes.has(id), `Unknown node: ${id}`);
    this.visibility.set(id, visible); this.refreshVisibility();
  }
  showAll(): void {
    for (const id of this.nodes.keys()) this.visibility.set(id, true);
    this.refreshVisibility();
  }
  isolate(ids: readonly string[]): void {
    const allowed = new Set<string>();
    const children = new Map<string, string[]>();
    for (const node of this.nodes.values()) if (node.parentId !== undefined) {
      const list = children.get(node.parentId) ?? []; list.push(node.id); children.set(node.parentId, list);
    }
    for (const id of ids) {
      invariant(this.nodes.has(id), `Unknown node: ${id}`);
      let node = this.nodes.get(id);
      while (node) { allowed.add(node.id); node = node.parentId === undefined ? undefined : this.nodes.get(node.parentId); }
      const queue = [id];
      for (let i = 0; i < queue.length; i++) { allowed.add(queue[i]); queue.push(...(children.get(queue[i]) ?? [])); }
    }
    for (const id of this.nodes.keys()) this.visibility.set(id, allowed.has(id));
    this.refreshVisibility();
  }
  private refreshVisibility(): void {
    const effective = new Map<string, boolean>();
    for (const start of this.nodes.values()) {
      const path: ModelNode[] = [];
      let node: ModelNode | undefined = start;
      while (node && !effective.has(node.id)) {
        path.push(node); node = node.parentId === undefined ? undefined : this.nodes.get(node.parentId);
      }
      let visible = node ? effective.get(node.id) !== false : true;
      for (let i = path.length - 1; i >= 0; i--) {
        visible = visible && this.visibility.get(path[i].id) !== false;
        effective.set(path[i].id, visible);
      }
    }
    for (const [id, instance] of this.instances) instance.group.visible = effective.get(id) !== false;
  }
  visibleBounds(): THREE.Box3 {
    this.root.updateMatrixWorld(true);
    const box = new THREE.Box3();
    for (const instance of this.instances.values()) if (instance.group.visible) box.union(new THREE.Box3().setFromObject(instance.group));
    return box;
  }
  setClippingPlanes(planes: THREE.Plane[]): void {
    this.planes = planes;
    for (const material of this.materials) { material.clippingPlanes = planes; material.needsUpdate = true; }
    if (this.highlight) { this.highlight.material.clippingPlanes = planes; this.highlight.material.needsUpdate = true; }
  }
  clearHighlight(): void {
    if (!this.highlight) return;
    this.highlight.removeFromParent(); this.highlight.geometry.dispose(); this.highlight.material.dispose();
    this.highlight = undefined;
  }
  highlightSelection(selection: Selection | null): void {
    this.clearHighlight();
    if (!selection || !isSelectionValid(this.document, selection)) return;
    const instance = this.instances.get(selection.nodeId);
    if (!instance) return;
    const geometry = new THREE.BufferGeometry();
    if (selection.kind === "edge") {
      const edge = instance.asset.source.edges?.find((edge) => edge.id === selection.edgeId);
      if (!edge) { geometry.dispose(); return; }
      const points = centeredPositions(edge.positions, instance.asset.center);
      const segments = new Float32Array((points.length / 3 - 1) * 6);
      for (let p = 0, s = 0; p < points.length - 3; p += 3, s += 6) segments.set(points.subarray(p, p + 6), s);
      geometry.setAttribute("position", new THREE.BufferAttribute(segments, 3));
      this.highlight = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: this.theme.selection, depthTest: true, clippingPlanes: this.planes }));
    } else {
      const indices = selectedTriangleIndices(instance.asset.source, selection);
      const positions = instance.asset.triangles.getAttribute("position");
      // Independent highlight buffers: disposing a highlight never deletes a shared GL attribute.
      const selected = new Float32Array(indices.length * 3);
      for (let i = 0; i < indices.length; i++) {
        selected[i * 3] = positions.getX(indices[i]); selected[i * 3 + 1] = positions.getY(indices[i]); selected[i * 3 + 2] = positions.getZ(indices[i]);
      }
      geometry.setAttribute("position", new THREE.BufferAttribute(selected, 3));
      this.highlight = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: this.theme.selection,
        transparent: true, opacity: 0.58, depthWrite: false, depthTest: true, side: THREE.DoubleSide,
        polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, clippingPlanes: this.planes }));
    }
    this.highlight.renderOrder = 10; instance.group.add(this.highlight);
  }
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true; this.clearHighlight();
    this.root.removeFromParent(); this.root.clear();
    for (const geometry of this.geometries) geometry.dispose();
    for (const material of this.materials) material.dispose();
    this.geometries.clear(); this.materials.clear(); this.instances.clear();
  }
}
