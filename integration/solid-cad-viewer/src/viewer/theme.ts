export interface ViewerTheme {
  background: string;
  surface: string;
  edge: string;
  selection: string;
  panel: string;
  text: string;
  muted: string;
  border: string;
}
export const DEFAULT_THEME: ViewerTheme = {
  background: "#111821", surface: "#94a8ba", edge: "#233449", selection: "#ffb454",
  panel: "#192431", text: "#e4edf6", muted: "#aabccc", border: "#35465a",
};
