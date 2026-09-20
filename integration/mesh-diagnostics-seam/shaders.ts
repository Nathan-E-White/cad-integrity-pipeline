/** GPU display transforms only. The authoritative coordinates never change. */
export const surfaceVertex = /* glsl */ `
  attribute vec3 aCenter;
  attribute vec3 aBarycentric;
  attribute vec3 aColor;
  attribute float aSelected;
  uniform float uShrink;
  varying vec3 vBarycentric;
  varying vec3 vColor;
  varying vec3 vPosition;
  varying vec3 vViewPosition;
  varying vec3 vCenter;
  varying float vSelected;
  void main() {
    vec3 displayed = aCenter + uShrink * (position - aCenter);
    vPosition = displayed;
    vCenter = aCenter;
    vBarycentric = aBarycentric;
    vColor = aColor;
    vSelected = aSelected;
    vec4 viewed = modelViewMatrix * vec4(displayed, 1.0);
    vViewPosition = viewed.xyz;
    gl_Position = projectionMatrix * viewed;
  }
`;
export const surfaceFragment = /* glsl */ `
  uniform bool uClip;
  uniform vec4 uPlane;
  uniform bool uPeel;
  uniform vec3 uPeelCenter;
  uniform float uPeelRadius;
  uniform bool uHeatmap;
  uniform bool uWire;
  uniform bool uWireOnly;
  uniform bool uSelectionPass;
  uniform bool uIsolate;
  uniform float uOpacity;
  uniform vec3 uSurfaceColor;
  uniform vec3 uWireColor;
  uniform vec3 uSelectedColor;
  varying vec3 vBarycentric;
  varying vec3 vColor;
  varying vec3 vPosition;
  varying vec3 vViewPosition;
  varying vec3 vCenter;
  varying float vSelected;
  void main() {
    if (uClip && dot(uPlane.xyz, vPosition) + uPlane.w < 0.0) discard;
    // A radial face-centroid filter, NOT a volume or topology-aware peel.
    if (uPeel && distance(vCenter, uPeelCenter) > uPeelRadius) discard;
    if ((uSelectionPass || uIsolate) && vSelected < 0.5) discard;
    vec3 width = max(fwidth(vBarycentric) * 1.15, vec3(0.000001));
    vec3 interior = smoothstep(vec3(0.0), width, vBarycentric);
    float edge = 1.0 - min(min(interior.x, interior.y), interior.z);
    vec3 n = normalize(cross(dFdx(vViewPosition), dFdy(vViewPosition)));
    float lighting = 0.50 + 0.50 * abs(dot(n, normalize(vec3(0.35, 0.55, 1.0))));
    vec3 color = uHeatmap ? vColor : uSurfaceColor * lighting;
    float alpha = uOpacity;
    if (uWireOnly) { color = uWireColor; alpha *= edge; if (alpha < 0.01) discard; }
    else if (uWire && !uSelectionPass) color = mix(color, uWireColor, edge * 0.38);
    if (uSelectionPass) color = uSelectedColor;
    gl_FragColor = vec4(color, alpha);
    #include <colorspace_fragment>
  }
`;
