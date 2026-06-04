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
