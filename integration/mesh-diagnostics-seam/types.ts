import type { ILoadingStatus } from "@gradio/statustracker";
import type { InspectorDocument } from "./src/core/contracts.js";
export interface InspectorProps { value: InspectorDocument | null; }
export interface InspectorEvents { clear_status: ILoadingStatus; }
