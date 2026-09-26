import * as T from 'three';
import type { QuadTrace } from '../core/inspection';
import type { DisplayFrame } from '../../../../../integration/mesh-diagnostics-seam/src/core/math';
import { displayPositions } from '../../../../../integration/mesh-diagnostics-seam/src/core/math';
import { ResourceScope } from '../../../../../integration/mesh-diagnostics-seam/src/render/ResourceScope';

/** One immutable line batch; selection only updates its scalar emphasis buffer. */
export class TraceOverlay {
    readonly group = new T.Group();
    private scope = new ResourceScope();
    private geometry: T.BufferGeometry;
    private material: T.ShaderMaterial;
    private owners: number[];
    private selected: number | null | undefined;
    constructor(trace: QuadTrace, frame: DisplayFrame) {
        const coordinates = trace.segments.flatMap(segment => segment.coordinates);
        this.owners = trace.segments.flatMap(segment => [segment.trace_id, segment.trace_id]);
        this.geometry = this.scope.own(new T.BufferGeometry());
        this.geometry.setAttribute('position', new T.BufferAttribute(displayPositions(coordinates, frame), 3));
        this.geometry.setAttribute('emphasis', new T.BufferAttribute(new Float32Array(this.owners.length), 1).setUsage(T.DynamicDrawUsage));
        this.material = this.scope.own(new T.ShaderMaterial({ transparent: true, depthWrite: false,
            uniforms: { clip: { value: new T.Vector4(0, 0, 0, 1) } },
            vertexShader: `attribute float emphasis;varying float strength;varying vec3 location;void main(){strength=emphasis;location=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
            fragmentShader: `varying float strength;varying vec3 location;uniform vec4 clip;void main(){if(dot(clip.xyz,location)+clip.w<0.0)discard;gl_FragColor=vec4(mix(vec3(.15,.72,.95),vec3(1.,.82,.2),strength),mix(.58,1.,strength));}`,
        }));
        const lines = new T.LineSegments(this.geometry, this.material); lines.renderOrder = 4; this.group.add(lines);
    }
    update(selected: number | null, _xray: boolean, plane: T.Vector4): void {
        if (selected !== this.selected) {
            this.selected = selected;
            const emphasis = this.geometry.getAttribute('emphasis') as T.BufferAttribute;
            for (let i = 0; i < this.owners.length; i++) emphasis.setX(i, selected === this.owners[i] ? 1 : 0);
            emphasis.needsUpdate = true;
        }
        // These are evidence lines, not source edges; keep them legible on coincident faces.
        this.material.depthTest = false; this.material.uniforms.clip.value.copy(plane);
    }
    dispose(): void { this.group.removeFromParent(); this.scope.dispose(); }
}
