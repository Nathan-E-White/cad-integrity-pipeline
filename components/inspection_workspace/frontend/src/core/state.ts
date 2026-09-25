import type { Kind, Target } from './inspection';
export type Pane = 'original' | 'candidate';
export interface Clip {
    enabled: boolean;
    axis: 0 | 1 | 2;
    offset: number;
}
export interface WorkspaceState {
    active: Pane;
    mode: Kind;
    category: string | null;
    defectsOnly: boolean;
    selections: Record<Pane, Target | null>;
    hover: Record<Pane, Target | null>;
    maximized: Pane | null;
    compactDocks: boolean;
    restoreCompactDocks: boolean | null;
    linkedCameras: boolean;
    linkedClipping: boolean;
    clips: Record<Pane, Clip>;
    xray: boolean;
    hiddenCategories: string[];
}
export const initialState = (faceKind: 'polygonal_face' | 'native_face' = 'polygonal_face', compactDocks = false): WorkspaceState => ({ active: 'original', mode: faceKind, category: null, defectsOnly: faceKind !== 'native_face',
    selections: { original: null, candidate: null }, hover: { original: null, candidate: null }, maximized: null, compactDocks, restoreCompactDocks: null, linkedCameras: true, linkedClipping: true,
    clips: { original: { enabled: false, axis: 0, offset: 0 }, candidate: { enabled: false, axis: 0, offset: 0 } }, xray: false, hiddenCategories: [] });
export type Action = {
    type: 'select' | 'hover';
    pane: Pane;
    target: Target | null;
} | {
    type: 'active';
    pane: Pane;
} | {
    type: 'mode';
    mode: Kind;
} | {
    type: 'category';
    category: string | null;
} | {
    type: 'defects';
    value: boolean;
} | {
    type: 'maximize';
    pane: Pane | null;
} | {
    type: 'clip';
    pane: Pane;
    clip: Clip;
} | {
    type: 'docks';
    compact: boolean;
} | {
    type: 'cameraLink';
    value: boolean;
} | {
    type: 'link';
    value: boolean;
} | {
    type: 'xray';
    value: boolean;
} | {
    type: 'visibility';
    category: string;
};
export function transition(state: WorkspaceState, action: Action): WorkspaceState {
    switch (action.type) {
        case 'select': return { ...state, selections: { ...state.selections, [action.pane]: action.target }, hover: { ...state.hover, [action.pane]: null } };
        case 'hover': return { ...state, hover: { ...state.hover, [action.pane]: action.target } };
        case 'active': return { ...state, active: action.pane };
        case 'mode': return { ...state, mode: action.mode };
        case 'category': return { ...state, category: action.category };
        case 'defects': return { ...state, defectsOnly: action.value };
        case 'maximize': return action.pane === null
            ? { ...state, maximized: null, compactDocks: state.restoreCompactDocks ?? state.compactDocks, restoreCompactDocks: null }
            : { ...state, maximized: action.pane, compactDocks: false, restoreCompactDocks: state.compactDocks };
        case 'docks': return { ...state, compactDocks: action.compact };
        case 'cameraLink': return { ...state, linkedCameras: action.value };
        case 'xray': return { ...state, xray: action.value };
        case 'visibility': return { ...state, hiddenCategories: state.hiddenCategories.includes(action.category) ? state.hiddenCategories.filter(c => c !== action.category) : [...state.hiddenCategories, action.category] };
        case 'clip': return { ...state, clips: state.linkedClipping ? { original: action.clip, candidate: action.clip } : { ...state.clips, [action.pane]: action.clip } };
        case 'link': return { ...state, linkedClipping: action.value, clips: action.value ? { original: state.clips[state.active], candidate: state.clips[state.active] } : state.clips };
    }
}
/** A filter changes emphasis, never the pinned target. */
export function targetOutsideFilter(mesh: import('./inspection').Mesh, target: Target | null, category: string | null, defectsOnly: boolean): boolean {
    if (!target)
        return false;
    if (target.type === 'category')
        return category !== null && target.categoryId !== category;
    const memberships = mesh.categories.filter(c => c.kind === target.kind && c.entity_ids.includes(target.entityId));
    return category !== null ? !memberships.some(c => c.id === category) : defectsOnly && memberships.length === 0;
}
