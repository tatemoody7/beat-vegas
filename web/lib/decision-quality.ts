import { parseFactors } from "@/lib/score";
import { prisma } from "@/lib/prisma";

export type DqPickRow = {
  result: string | null;
  line: number | null;
  model_line_at_pick: number | null;
  opening_line: number | null;
  closing_line: number | null;
  clv: number | null;
  clv_prob: number | null; // no-vig PRICE CLV (prob points), juice only
  factors_json_at_pick: string | null;
};

export type Bucket = {
  n: number;
  wins: number;
  decided: number;
  hitPct: number | null;
};

function tally(picks: DqPickRow[]): Bucket {
  const wins = picks.filter((p) => p.result === "under").length;
  const decided = picks.filter(
    (p) => p.result === "under" || p.result === "over",
  ).length;
  return {
    n: picks.length,
    wins,
    decided,
    hitPct: decided ? (100 * wins) / decided : null,
  };
}

export function beatMyModel(picks: DqPickRow[]): {
  agreed: Bucket;
  against: Bucket;
} {
  // Only picks where we know our model's line at pick time can be compared.
  // edge = line taken - our model line; > 0 = our model agreed under is favorable.
  const withEdge = picks
    .filter((p) => p.line != null && p.model_line_at_pick != null)
    .map((p) => ({
      pick: p,
      edge: (p.line as number) - (p.model_line_at_pick as number),
    }));
  const agreed = withEdge.filter((e) => e.edge > 0).map((e) => e.pick);
  const against = withEdge.filter((e) => e.edge <= 0).map((e) => e.pick);
  return { agreed: tally(agreed), against: tally(against) };
}

// WHICH SIGN IS GOOD, because it is the opposite of the obvious guess.
//
// manual_picks.clv is grading.py::clv_under = closing - bet, a plain factual
// difference. Every bet here is an UNDER, and for an under a HIGHER number is
// easier to win. So a line that FALLS after you bet leaves you holding the
// better ticket: bet u28.5, close 27.5, clv = -1, and you have a point of
// cushion the closing bettor does not. The glossary has always said it --
// "for an under, the total going down afterwards is good" -- but this file
// counted clv > 0 as "moved your way" and the Results page printed that under
// exactly that label, so it reported the share that moved AGAINST you.
//
// Measured on week 2: three of Tate's six tickets moved his way and none moved
// against him; the page said 0%.
//
// Stored values are unchanged. `favourable` is the one place the direction
// lives, and clvDirection.test.ts pins it so it cannot quietly flip back.
const favourable = (clv: number): boolean => clv < 0;

export function clvSummary(picks: DqPickRow[]): {
  n: number;
  avg: number | null;
  /** Share whose line moved TOWARD the under after the bet. */
  pctFavourable: number | null;
  /** Hit rate of the bets whose line moved toward them, and away from them. */
  favClvHitPct: number | null;
  advClvHitPct: number | null;
  /** Mean points the line moved toward the under; positive reads as good. */
  avgPointsGained: number | null;
  // No-vig PRICE CLV (juice dimension only): avg in percentage points, share +.
  // This one IS positive-is-good already -- a rising no-vig under price means
  // the market moved toward the under, so an early under got the cheaper side.
  nPrice: number;
  avgPricePp: number | null;
  pctPricePositive: number | null;
} {
  const withClv = picks.filter((p) => p.clv != null);
  const n = withClv.length;
  const avg = n ? withClv.reduce((a, p) => a + (p.clv as number), 0) / n : null;
  const positive = withClv.filter((p) => favourable(p.clv as number));
  const pos = tally(positive);
  const neg = tally(withClv.filter((p) => !favourable(p.clv as number)));
  const withPrice = picks.filter((p) => p.clv_prob != null);
  const nPrice = withPrice.length;
  const pricePos = withPrice.filter((p) => (p.clv_prob as number) > 0).length;
  return {
    n,
    avg,
    pctFavourable: n ? (100 * positive.length) / n : null,
    favClvHitPct: pos.hitPct,
    advClvHitPct: neg.hitPct,
    // Sign-flipped so the number on the page reads the way a reader expects:
    // +1.7 means the market came 1.7 points toward the under after we bet.
    avgPointsGained: avg === null ? null : -avg,
    nPrice,
    avgPricePp: nPrice
      ? (100 * withPrice.reduce((a, p) => a + (p.clv_prob as number), 0)) /
        nPrice
      : null,
    pctPricePositive: nPrice ? (100 * pricePos) / nPrice : null,
  };
}

export function timingSummary(picks: DqPickRow[]): {
  nOpen: number;
  pctAtOrBetterThanOpen: number | null;
  nClose: number;
  pctBeatingClose: number | null;
} {
  // UNDER bettor: a higher line taken is a better number.
  const withOpen = picks.filter(
    (p) => p.line != null && p.opening_line != null,
  );
  const atOrBetter = withOpen.filter(
    (p) => (p.line as number) >= (p.opening_line as number),
  );
  const withClose = picks.filter(
    (p) => p.line != null && p.closing_line != null,
  );
  const beatClose = withClose.filter(
    (p) => (p.line as number) > (p.closing_line as number),
  );
  return {
    nOpen: withOpen.length,
    pctAtOrBetterThanOpen: withOpen.length
      ? (100 * atOrBetter.length) / withOpen.length
      : null,
    nClose: withClose.length,
    pctBeatingClose: withClose.length
      ? (100 * beatClose.length) / withClose.length
      : null,
  };
}

export type LedgerRates = Record<string, { mean: number; n: number }>;

export type FactorAttribution = {
  key: string;
  label: string;
  n: number;
  wins: number;
  decided: number;
  yourHitPct: number | null;
  ledgerHitPct: number | null;
  weight: "under" | "over" | "even";
};

export function perFactorAttribution(
  picks: DqPickRow[],
  ledger: LedgerRates,
): FactorAttribution[] {
  // factor key -> {label, picks where it was green}
  const acc = new Map<string, { label: string; rows: DqPickRow[] }>();
  for (const p of picks) {
    const board = parseFactors(p.factors_json_at_pick).factor_board ?? [];
    for (const f of board) {
      if (f.color !== "green") continue;
      const e = acc.get(f.key) ?? { label: f.label, rows: [] };
      e.rows.push(p);
      acc.set(f.key, e);
    }
  }
  const out: FactorAttribution[] = [];
  for (const [key, { label, rows }] of acc) {
    const b = tally(rows);
    const ledgerHitPct = ledger[key] ? 100 * ledger[key].mean : null;
    let weight: "under" | "over" | "even" = "even";
    if (b.hitPct != null && ledgerHitPct != null) {
      if (b.hitPct > ledgerHitPct + 1) weight = "under";
      else if (b.hitPct < ledgerHitPct - 1) weight = "over";
    }
    out.push({
      key,
      label,
      n: b.n,
      wins: b.wins,
      decided: b.decided,
      yourHitPct: b.hitPct,
      ledgerHitPct,
      weight,
    });
  }
  return out.sort((a, b) => b.n - a.n);
}

export type DecisionQuality = {
  beatModel: ReturnType<typeof beatMyModel>;
  clv: ReturnType<typeof clvSummary>;
  timing: ReturnType<typeof timingSummary>;
  factors: FactorAttribution[];
  n: number;
};

export type Ledger = "real" | "paper";

/**
 * One ledger at a time. Until 2026-09-22 this pooled paper and real rows into
 * a panel headed "Your decisions" -- ~75% of which were the card's paper
 * picks. The two ledgers are split everywhere else in the app; they are split
 * here too.
 */
export async function getDecisionQuality(
  season: number,
  which: Ledger = "real",
): Promise<DecisionQuality> {
  const isPaper = which === "paper";
  const picks = await prisma.$queryRaw<DqPickRow[]>`
    SELECT result, line, model_line_at_pick, opening_line, closing_line, clv,
           clv_prob, factors_json_at_pick
    FROM manual_picks
    WHERE season = ${season} AND graded = true
      AND COALESCE(is_paper, false) = ${isPaper}
  `;
  // factor_ledger may not exist yet (created by the Phase-3 Python jobs on
  // their next Neon write). Degrade to no ledger rather than throwing.
  let ledgerRows: {
    factor: string;
    post_mean: number | null;
    n: number | bigint | null;
  }[] = [];
  try {
    ledgerRows = await prisma.$queryRaw`
      SELECT factor, post_mean, n FROM factor_ledger
    `;
  } catch (err) {
    // factor_ledger may not exist yet (created lazily by the Phase-3 Python jobs).
    // Degrade to no ledger, but surface real DB problems (connection/permission/
    // typo) instead of silently masquerading them as "no ledger".
    console.warn(
      "getDecisionQuality: factor_ledger unavailable, degrading",
      err,
    );
    ledgerRows = [];
  }
  const ledger: LedgerRates = {};
  for (const r of ledgerRows) {
    if (r.post_mean != null)
      ledger[r.factor] = { mean: r.post_mean, n: Number(r.n ?? 0) };
  }
  return {
    beatModel: beatMyModel(picks),
    clv: clvSummary(picks),
    timing: timingSummary(picks),
    factors: perFactorAttribution(picks, ledger),
    n: picks.length,
  };
}
