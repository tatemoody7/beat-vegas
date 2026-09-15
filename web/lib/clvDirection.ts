// The ONE place the sign of a stored line value is turned into a displayed one.
//
// manual_picks.clv is `closing − bet` (beatvegas/grading.py::clv_under). Every bet
// is an UNDER and a higher number is easier, so a line that FALLS after the bet is
// the good outcome: negative stored clv is favourable. The site shows it the way a
// reader expects — positive means the market came toward you — so display negates.
// record.ts and decision-quality.ts apply the same rule; PicksList printed the raw
// value until 2026-09-15 (a −1.00 that was in fact a point in Tate's favour).
export function displayLineValue(
  clv: number | null | undefined,
): number | null {
  return clv === null || clv === undefined || Number.isNaN(clv) ? null : -clv;
}
