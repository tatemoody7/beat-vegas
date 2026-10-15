// The units chart's Y axis on Results (BankrollCurve.tsx), kept pure for tests.

/** Even, whole-unit axis labels from the floor to the ceiling, every unit up
 *  to 8 units of range and every 2 beyond (Tate 2026-10-15, Q9: the old axis
 *  read +4u, +3u, +1u, -1u, -3u). Zero is always one of them. */
export function curveTicks(lo: number, hi: number): number[] {
  const bottom = Math.floor(lo);
  const top = Math.ceil(hi);
  const step = top - bottom > 8 ? 2 : 1;
  const out: number[] = [];
  // Extend past the data on both sides so the domain never clips a point.
  for (let v = 0; ; v -= step) {
    out.unshift(v);
    if (v <= bottom) break;
  }
  for (let v = step; out[out.length - 1] < top; v += step) out.push(v);
  return out;
}
