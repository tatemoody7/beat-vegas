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
  const edge = (p: DqPickRow) =>
    p.line != null && p.model_line_at_pick != null
      ? p.line - p.model_line_at_pick
      : null;
  // edge > 0 = market line above our model line = our model agreed under is favorable.
  const agreed = picks.filter((p) => (edge(p) ?? -1) > 0);
  const against = picks.filter((p) => (edge(p) ?? -1) <= 0);
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
