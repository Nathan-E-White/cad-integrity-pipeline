import type { ILoadingStatus as LoadingStatus } from "@gradio/statustracker";

export type AuditCategory = "geometry" | "topology" | "execution";

export interface DeltaAuditRow {
	category: AuditCategory;
	entity: string;
	before: string;
	after: string;
	delta: string;
}

export interface DeltaAuditValue {
	title: string;
	rows: DeltaAuditRow[];
}

export interface DeltaAuditProps {
	value: DeltaAuditValue | null;
}

export interface DeltaAuditEvents {
	clear_status: LoadingStatus;
}
