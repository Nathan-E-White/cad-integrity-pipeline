/** One scale drives both the CSS legend and GPU attributes. Not a validity oracle. */
export const SCALE = ["#b2182b", "#ef8a62", "#f7f7f7", "#67a9cf", "#2166ac"] as const;
export const MISSING_COLOR = "#9ca3af";
type RGB = [number, number, number];
const rgb = (hex: string): RGB => [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16) / 255) as RGB;
export const srgbToLinear = (c: number): number => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
export function scalarColor(value: number | null, domain: readonly [number, number]): RGB {
  if (value === null || !Number.isFinite(value)) return rgb(MISSING_COLOR);
  const t = Math.min(1, Math.max(0, (value - domain[0]) / (domain[1] - domain[0]))) * (SCALE.length - 1);
  const i = Math.min(SCALE.length - 2, Math.floor(t)), f = t - i;
  const a = rgb(SCALE[i]), b = rgb(SCALE[i + 1]);
  return a.map((v, k) => v + f * (b[k] - v)) as RGB;
}
export const legendGradient = `linear-gradient(to right, ${SCALE.join(", ")})`;
export function faceColors(values: readonly (number | null)[], domain: readonly [number, number]): Float32Array {
  const out = new Float32Array(values.length * 9);
  values.forEach((v, face) => {
    const linear = scalarColor(v, domain).map(srgbToLinear);
    for (let corner = 0; corner < 3; corner++) out.set(linear, face * 9 + corner * 3);
  });
  return out;
}
