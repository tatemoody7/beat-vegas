// No-vig (devigged) fair-probability math for two-way totals.
// Exact mirror of beatvegas/devig.py — keep the two in sync (same test vectors).
// Devig outputs are MARKET signal: use only for CLV, line-check EV, and staking
// — never feed them into the market-blind BV regressor.

export function americanToDecimal(price: number): number {
  return price < 0 ? 1 + 100 / Math.abs(price) : 1 + price / 100;
}

export function americanToProb(price: number): number {
  return 1 / americanToDecimal(price);
}

function multiplicative(pOver: number, pUnder: number): [number, number] {
  const total = pOver + pUnder;
  return [pOver / total, pUnder / total];
}

// Find k such that pOver**k + pUnder**k == 1, via bisection.
function power(pOver: number, pUnder: number): [number, number] {
  let lo = 0;
  let hi = 10;
  for (let i = 0; i < 60; i++) {
    const k = (lo + hi) / 2;
    const s = pOver ** k + pUnder ** k;
    if (s > 1) lo = k;
    else hi = k;
  }
  const k = (lo + hi) / 2;
  return [pOver ** k, pUnder ** k];
}

// Shin two-outcome devig: solve for the insider proportion z in (0, 0.5) by
// bisection on sqrt(z^2+4(1-z)a) + sqrt(z^2+4(1-z)b) = 2.
function shin(pOver: number, pUnder: number): [number, number] {
  const booksum = pOver + pUnder;
  if (booksum <= 1) return multiplicative(pOver, pUnder);
  const a = (pOver * pOver) / booksum;
  const b = (pUnder * pUnder) / booksum;
  const s = (z: number) =>
    Math.sqrt(z * z + 4 * (1 - z) * a) + Math.sqrt(z * z + 4 * (1 - z) * b);
  let lo = 0;
  let hi = 0.5;
  for (let i = 0; i < 60; i++) {
    const z = (lo + hi) / 2;
    if (s(z) > 2) lo = z;
    else hi = z;
  }
  const z = (lo + hi) / 2;
  const fair = (p: number) =>
    (Math.sqrt(z * z + 4 * (1 - z) * ((p * p) / booksum)) - z) / (2 * (1 - z));
  return [fair(pOver), fair(pUnder)];
}

export type DevigMethod = "multiplicative" | "power" | "shin";

// Returns { fairOver, fairUnder, hold }. The two fair probs sum to 1; hold is
// the book's overround (raw implied-prob sum - 1).
export function devigTwoWay(
  overPrice: number,
  underPrice: number,
  method: DevigMethod = "multiplicative",
): { fairOver: number; fairUnder: number; hold: number } {
  const pOver = americanToProb(overPrice);
  const pUnder = americanToProb(underPrice);
  const hold = pOver + pUnder - 1;
  let fo: number;
  let fu: number;
  if (method === "multiplicative") [fo, fu] = multiplicative(pOver, pUnder);
  else if (method === "power") [fo, fu] = power(pOver, pUnder);
  else if (method === "shin") [fo, fu] = shin(pOver, pUnder);
  else throw new Error(`unknown devig method: ${method}`);
  return { fairOver: fo, fairUnder: fu, hold };
}

// Per-$1 EV of taking the UNDER at `offeredUnderPrice`, given a reference no-vig
// fair under probability. Positive = +EV.
export function evUnder(
  fairUnderProb: number,
  offeredUnderPrice: number,
): number {
  const payout = americanToDecimal(offeredUnderPrice) - 1;
  return fairUnderProb * payout - (1 - fairUnderProb);
}
