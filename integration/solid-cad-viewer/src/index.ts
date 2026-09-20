export * from "./model";
export * from "./math";
export * from "./selection";
export * from "./data/sources";
export * from "./data/npz";
export * from "./data/wire";
export * from "./data/NpzWorkerSource";
export * from "./viewer/CadViewer";
export * from "./viewer/ViewerPanel";
export * from "./viewer/RemoteCadViewer";
export * from "./viewer/theme";
export type { DisplayMode } from "./viewer/RenderModel";
// Type-only export: importing UI/data APIs does not eagerly pull the rendering engine into SSR.
export type { ThreeCadViewer, ViewerOptions, ViewerLayer, ViewerLayerContext, ClipPlane, Projection, ViewPreset } from "./viewer/ThreeCadViewer";
