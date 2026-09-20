import { createQuery } from "@tanstack/solid-query";
import { createSignal, type JSX, onMount, Show, Suspense } from "solid-js";
import type { ModelSource } from "../data/sources";
import { ViewerPanel, type ViewerPanelProps } from "./ViewerPanel";

export interface RemoteCadViewerProps extends Omit<ViewerPanelProps, "document"> { readonly source: ModelSource; }
/** Put a QueryClientProvider above this component. Keep binary documents out of SSR dehydration. */
export function RemoteCadViewer(props: RemoteCadViewerProps): JSX.Element {
  const [mounted, setMounted] = createSignal(false);
  onMount(() => setMounted(true));
  const query = createQuery(() => {
    const source = props.source;
    return {
      queryKey: ["cad-model", ...source.cacheKey],
      queryFn: ({ signal }: { signal: AbortSignal }) => source.load(signal),
      enabled: mounted(), structuralSharing: false as const,
      staleTime: Infinity, gcTime: 60_000, retry: false,
      refetchOnWindowFocus: false, refetchOnReconnect: false, throwOnError: false,
    };
  });
  return (
    <div class="cad-remote">
      <Show when={query.isFetching}><p role="status">Loading geometry…</p></Show>
      <Show when={query.error}>{(error) => <p role="alert">{error().message} <button type="button" onClick={() => void query.refetch()}>Retry</button></p>}</Show>
      <Suspense fallback={<div class="cad-loading" style={{ height: props.height ?? "600px" }} role="status">Preparing geometry…</div>}>
        <ViewerPanel document={query.data ?? null} height={props.height} theme={props.theme} clippingPlane={props.clippingPlane}
          onReady={props.onReady} onSelectionChange={props.onSelectionChange} onError={props.onError} />
      </Suspense>
    </div>
  );
}
