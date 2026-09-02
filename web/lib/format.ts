// Shared number formatting + small stats helpers. One copy, used by every lib
// module and page so a signed unit, a percent and a median always read the same.

/** "+1.25" / "-0.50" — signed with a fixed number of decimals. */
export const signed = (n: number, dp = 2): string =>
  `${n >= 0 ? "+" : ""}${n.toFixed(dp)}`;

/** Fixed-decimal number, "—" for null. */
export const fmt = (n: number | null | undefined, dp = 1): string =>
  n === null || n === undefined ? "—" : n.toFixed(dp);

/** Percent string from a 0–100 value: "54.0%"; "—" for null. */
export const pct = (v: number | null | undefined, dp = 1): string =>
  v === null || v === undefined ? "—" : `${v.toFixed(dp)}%`;

/** Percent string from a 0–1 fraction: "54.0%". */
export const pctOfFraction = (v: number | null | undefined, dp = 1): string =>
  v === null || v === undefined ? "—" : `${(100 * v).toFixed(dp)}%`;

/** Signed percent from a 0–1 fraction: "+1.2%". */
export const signedPctOfFraction = (
  v: number | null | undefined,
  dp = 1,
): string => (v === null || v === undefined ? "—" : `${signed(100 * v, dp)}%`);

/** American odds: "+105" / "-110". */
export const american = (p: number): string => (p > 0 ? `+${p}` : `${p}`);

/** Median of a list; null when empty. */
export function median(xs: number[]): number | null {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** Round to two decimals (line arithmetic). */
export const round2 = (n: number): number => Math.round(n * 100) / 100;
