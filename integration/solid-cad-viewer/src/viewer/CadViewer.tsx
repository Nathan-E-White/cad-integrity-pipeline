import { createEffect, createSignal, type JSX, on, onCleanup, onMount, Show } from "solid-js";
import type { ModelDocument, PickResult, Selection, SelectionMode } from "../model";
import type { DisplayMode } from "./RenderModel";
import type { ClipPlane, Projection, ThreeCadViewer } from "./ThreeCadViewer";
import type { ViewerTheme } from "./theme";
import "./viewer.css";

export interface CadViewerProps {
  readonly document: ModelDocument | null;
  readonly projection?: Projection;
  readonly displayMode?: DisplayMode;
  readonly selectionMode?: SelectionMode;
  readonly clippingPlane?: ClipPlane | null;
  /** Construction-time options. Remount to replace the theme/pixel-ratio cap. */
  readonly theme?: Partial<ViewerTheme>;
  readonly maxPixelRatio?: number;
  readonly class?: string;
  readonly style?: JSX.CSSProperties;
  readonly onReady?: (viewer: ThreeCadViewer) => void;
  readonly onSelectionChange?: (selection: Selection | null, hit: PickResult | null) => void;
  readonly onError?: (error: Error) => void;
}

/** Solid components are functions; the resource-owning class lives in ThreeCadViewer.ts. */
export function CadViewer(props: CadViewerProps): JSX.Element {
  let host: HTMLDivElement | undefined;
  const [viewer, setViewer] = createSignal<ThreeCadViewer>();
  const [error, setError] = createSignal<string>();
  const report = (cause: unknown) => {
    const error = cause instanceof Error ? cause : new Error(String(cause));
    setError(error.message); props.onError?.(error);
  };
  onMount(() => {
    let cancelled = false;
    let instance: ThreeCadViewer | undefined;
    // Register cleanup synchronously under Solid ownership, not inside the import promise.
    onCleanup(() => { cancelled = true; instance?.dispose(); });
    void import("./ThreeCadViewer").then(({ ThreeCadViewer }) => {
      if (cancelled || !host) return;
      try {
        instance = new ThreeCadViewer(host, {
          theme: props.theme, maxPixelRatio: props.maxPixelRatio,
          onSelectionChange: (selection, hit) => props.onSelectionChange?.(selection, hit), onError: report,
        });
        setViewer(instance); props.onReady?.(instance);
      } catch (cause) { report(cause); }
    }).catch((cause) => { if (!cancelled) report(cause); });
  });
  createEffect(on(() => [viewer(), props.document] as const, ([instance, document]) => {
    if (!instance) return;
    try { instance.setDocument(document); setError(undefined); } catch (cause) { report(cause); }
  }));
  createEffect(on(() => [viewer(), props.projection ?? "perspective"] as const, ([instance, projection]) => instance?.setProjection(projection)));
  createEffect(on(() => [viewer(), props.displayMode ?? "shaded-edges"] as const, ([instance, mode]) => instance?.setDisplayMode(mode)));
  createEffect(on(() => [viewer(), props.selectionMode ?? "face"] as const, ([instance, mode]) => instance?.setSelectionMode(mode)));
  createEffect(on(() => [viewer(), props.clippingPlane ?? null] as const, ([instance, plane]) => {
    try { instance?.setClippingPlane(plane); } catch (cause) { report(cause); }
  }));
  return (
    <div class={`cad-canvas-shell ${props.class ?? ""}`} style={props.style}>
      <div class="cad-canvas-host" ref={(element) => { host = element; }} />
      <Show when={error()}>{(message) => <div class="cad-error" role="alert">{message()}</div>}</Show>
    </div>
  );
}
