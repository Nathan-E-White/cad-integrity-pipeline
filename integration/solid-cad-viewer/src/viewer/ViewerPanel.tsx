import { createMemo, createSignal, type JSX } from "solid-js";
import type { ModelDocument, PickResult, Selection, SelectionMode } from "../model";
import { CadViewer } from "./CadViewer";
import type { DisplayMode } from "./RenderModel";
import { DEFAULT_THEME, type ViewerTheme } from "./theme";
import type { ClipPlane, Projection, ThreeCadViewer, ViewPreset } from "./ThreeCadViewer";

export interface ViewerPanelProps {
  readonly document: ModelDocument | null;
  readonly height?: string;
  readonly theme?: Partial<ViewerTheme>;
  readonly clippingPlane?: ClipPlane | null;
  readonly onReady?: (viewer: ThreeCadViewer) => void;
  readonly onSelectionChange?: (selection: Selection | null, hit: PickResult | null) => void;
  readonly onError?: (error: Error) => void;
}
export function ViewerPanel(props: ViewerPanelProps): JSX.Element {
  const [viewer, setViewer] = createSignal<ThreeCadViewer>();
  const [projection, setProjection] = createSignal<Projection>("perspective");
  const [displayMode, setDisplayMode] = createSignal<DisplayMode>("shaded-edges");
  const [selectionMode, setSelectionMode] = createSignal<SelectionMode>("face");
  const [selection, setSelection] = createSignal<Selection | null>(null);
  const stats = createMemo(() => {
    const doc = props.document;
    const triangles = new Map(doc?.geometries.map((g) => [g.id, g.indices.length / 3]));
    return { instances: doc?.nodes.filter((n) => n.geometryId).length ?? 0,
      triangles: doc?.nodes.reduce((sum, n) => sum + (n.geometryId ? triangles.get(n.geometryId) ?? 0 : 0), 0) ?? 0 };
  });
  const selectedLabel = () => {
    const value = selection();
    if (!value) return "No selection";
    if (value.kind === "face") return `${value.nodeId} · ${value.faceKind} ${value.faceId}`;
    if (value.kind === "edge") return `${value.nodeId} · ${value.edgeKind} ${value.edgeId}`;
    if (value.kind === "triangle") return `${value.nodeId} · triangle ${value.triangleIndex}`;
    return value.nodeId;
  };
  const style = (): JSX.CSSProperties => {
    const theme = { ...DEFAULT_THEME, ...props.theme };
    return { height: props.height ?? "600px", "--cad-bg": theme.background, "--cad-panel": theme.panel,
      "--cad-text": theme.text, "--cad-muted": theme.muted, "--cad-border": theme.border, "--cad-accent": theme.selection };
  };
  return (
    <section class="cad-panel" style={style()} aria-label="Mesh and B-Rep viewer">
      <header class="cad-heading"><strong>{props.document?.name ?? "Geometry viewer"}</strong><span>Mesh / B-Rep</span></header>
      <div class="cad-toolbar" role="toolbar" aria-label="Viewer controls">
        <button type="button" onClick={() => viewer()?.fit()}>Fit</button>
        <label>Camera <select value={projection()} onChange={(e) => setProjection(e.currentTarget.value as Projection)}>
          <option value="perspective">Perspective</option><option value="orthographic">Orthographic</option>
        </select></label>
        <label>View <select aria-label="Standard view" onChange={(e) => viewer()?.setPreset(e.currentTarget.value as ViewPreset)}>
          <option value="isometric">Isometric</option><option value="front">Front</option><option value="back">Back</option>
          <option value="left">Left</option><option value="right">Right</option><option value="top">Top</option><option value="bottom">Bottom</option>
        </select></label>
        <label>Display <select value={displayMode()} onChange={(e) => setDisplayMode(e.currentTarget.value as DisplayMode)}>
          <option value="shaded-edges">Shaded + edges</option><option value="shaded">Shaded</option><option value="wireframe">Triangle wireframe</option>
        </select></label>
        <label>Pick <select value={selectionMode()} onChange={(e) => setSelectionMode(e.currentTarget.value as SelectionMode)}>
          <option value="face">Face / region</option><option value="edge">Explicit edge</option><option value="triangle">Triangle</option><option value="object">Object</option>
        </select></label>
        <button type="button" disabled={!selection()} onClick={() => { const selected = selection(); if (selected) viewer()?.isolate([selected.nodeId]); }}>Isolate</button>
        <button type="button" disabled={!selection()} onClick={() => { const selected = selection(); if (selected) viewer()?.setVisible(selected.nodeId, false); }}>Hide</button>
        <button type="button" onClick={() => viewer()?.showAll()}>Show all</button>
      </div>
      <CadViewer document={props.document} projection={projection()} displayMode={displayMode()} selectionMode={selectionMode()}
        theme={props.theme} clippingPlane={props.clippingPlane}
        onReady={(instance) => { setViewer(instance); props.onReady?.(instance); }}
        onSelectionChange={(selected, hit) => { setSelection(selected); props.onSelectionChange?.(selected, hit); }} onError={props.onError} />
      <footer class="cad-status" aria-live="polite">
        <span>{selectedLabel()}</span>
        <span>{stats().instances} instances · {stats().triangles.toLocaleString()} triangles · {props.document?.units ?? "unknown"}</span>
      </footer>
    </section>
  );
}
