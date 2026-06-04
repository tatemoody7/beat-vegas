import { parseFactors } from "@/lib/score";
import { prisma } from "@/lib/prisma";

export type DqPickRow = {
  result: string | null;
  line: number | null;
  model_line_at_pick: number | null;
  opening_line: number | null;
  closing_line: number | null;
  clv: number | null;
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

export function clvSummary(picks: DqPickRow[]): {
  n: number;
  avg: number | null;
  pctPositive: number | null;
  posClvHitPct: number | null;
  negClvHitPct: number | null;
} {
  const withClv = picks.filter((p) => p.clv != null);
  const n = withClv.length;
  const avg = n
    ? withClv.reduce((a, p) => a + (p.clv as number), 0) / n
    : null;
  const positive = withClv.filter((p) => (p.clv as number) > 0);
  const pos = tally(positive);
  const neg = tally(withClv.filter((p) => (p.clv as number) <= 0));
  return {
    n,
    avg,
    pctPositive: n ? (100 * positive.length) / n : null,
    posClvHitPct: pos.hitPct,
    negClvHitPct: neg.hitPct,
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
      key, label, n: b.n, wins: b.wins, decided: b.decided,
      yourHitPct: b.hitPct, ledgerHitPct, weight,
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

export async function getDecisionQuality(
  season: number,
): Promise<DecisionQuality> {
  const picks = await prisma.$queryRaw<DqPickRow[]>`
    SELECT result, line, model_line_at_pick, opening_line, closing_line, clv,
           factors_json_at_pick
    FROM manual_picks
    WHERE season = ${season} AND graded = true
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
    console.warn("getDecisionQuality: factor_ledger unavailable, degrading", err);
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
