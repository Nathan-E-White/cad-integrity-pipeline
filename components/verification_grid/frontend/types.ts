import type { ILoadingStatus as LoadingStatus } from "@gradio/statustracker";

export type VerificationState = "passed" | "failed" | "inconclusive";
export interface VerificationCheck { name: string; detail: string; state: VerificationState; }
export interface VerificationGroup { name: string; checks: VerificationCheck[]; }
export interface VerificationValue { title: string; summary: string; groups: VerificationGroup[]; }
export interface VerificationProps { value: VerificationValue | null; }
export interface VerificationEvents { clear_status: LoadingStatus; }
