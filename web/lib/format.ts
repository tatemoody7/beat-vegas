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

/** "won" -> "Won": first letter upper-cased, the rest untouched. */
export const capitalize = (s: string): string =>
  s.length === 0 ? s : s[0].toUpperCase() + s.slice(1);

/** Whole-dollar money: "$10", "$100". Stakes and bankrolls are never cents. */
export const usd = (n: number): string =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: Number.isInteger(n) ? 0 : 2,
  });

/**
 * CSS colour for a signed-units string ("+1.20" / "-0.55" / "—").
 *
 * Green and red are the OUTCOME colours, so only signed units get them —
 * never a win rate, never an ROI on its own. `null`/"—" is dim.
 *
 * Note flat zero: "0.00" does not start with "-", so it reads as good. That
 * is the long-standing behaviour on both the Results cards and the
 * post-mortem, kept deliberately here rather than changed in passing.
 */
export const unitColor = (s: string | undefined | null): string =>
  !s || s === "—"
    ? "var(--text-dim)"
    : s.startsWith("-")
      ? "var(--bad)"
      : "var(--good)";

/** One CSV cell: quoted (with doubled quotes) only when it needs to be; null
 *  and undefined are empty. Shared by every CSV export so they quote alike. */
export function csvCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
