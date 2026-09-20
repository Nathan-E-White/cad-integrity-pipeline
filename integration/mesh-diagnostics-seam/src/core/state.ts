export interface InspectionState {
  mode: "solid" | "ghost" | "wireframe";
  fieldId: string | null;
  shrink: number;
  wire: boolean;
  clipEnabled: boolean;
  clipAxis: 0 | 1 | 2;
  clipOffset: number;
  peelEnabled: boolean;
  radialFraction: number;
  isolate: boolean;
  xray: boolean;
  pulse: boolean;
}
export const defaultState = (): InspectionState => ({ mode: "solid", fieldId: null, shrink: 1, wire: true,
  clipEnabled: false, clipAxis: 0, clipOffset: 0, peelEnabled: false, radialFraction: 1,
  isolate: false, xray: false, pulse: false });
export function validateState(s: InspectionState): void {
  if (![s.shrink, s.clipOffset, s.radialFraction].every(Number.isFinite)) throw new Error("Nonfinite view state");
  if (s.shrink < 0.1 || s.shrink > 1 || s.radialFraction < 0 || s.radialFraction > 1 || ![0, 1, 2].includes(s.clipAxis)) {
    throw new Error("View state outside supported range");
  }
}
