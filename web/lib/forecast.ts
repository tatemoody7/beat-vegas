import { prisma } from "@/lib/prisma";
import { utcFrom } from "@/lib/armPositions";
import { etClock12 } from "@/lib/et";
import type { BoardFactor } from "@/lib/score";

// The game page's wind (Tate 2026-10-16): the steady wind at kickoff from the
// forecast the newest card build fetched (`build_forecasts`, written by
// beatvegas/wx_paper.capture -- the same row the wind strategies read), shown
// as one row in the factors list. It replaced the bare numbers of the Sunday `weather` table, which
// carried no fetch time: on 2026-10-16 they were ~6 days old and 19 of 47
// outdoor week-7 games read 5+ mph off the current forecast. Display only:
// the model does not read kickoff weather (LEAKY_WEATHER_COLS).

export type CardForecast = {
  fetchedAt: Date;
  leadHours: number | null;
  windMph: number | null;
  gustMph: number | null;
  temperatureF: number | null;
  precipitationIn: number | null;
  dome: boolean;
  model: string | null;
};

type Row = {
  fetched_at: string;
  lead_hours: number | null;
  wind_mph: number | null;
  wind_gust_mph: number | null;
  temperature_f: number | null;
  precipitation: number | null;
  dome: boolean | null;
  weather_model: string | null;
};

/** Pure: a stored row -> the page's shape. */
export function forecastFrom(r: Row): CardForecast {
  return {
    fetchedAt: utcFrom(r.fetched_at),
    leadHours: r.lead_hours,
    windMph: r.wind_mph,
    gustMph: r.wind_gust_mph,
    temperatureF: r.temperature_f,
    precipitationIn: r.precipitation,
    dome: r.dome === true,
    model: r.weather_model,
  };
}

const isMissingTable = (e: unknown): boolean =>
  typeof e === "object" &&
  e !== null &&
  String((e as { message?: string }).message ?? "").includes("does not exist");

/** The newest card-build forecast for a game, or null when no build has fetched one. */
export async function getCardForecast(
  gameId: number,
): Promise<CardForecast | null> {
  try {
    const rows = await prisma.$queryRaw<Row[]>`
      SELECT CAST(fetched_at AS TEXT) AS fetched_at, lead_hours, wind_mph,
             wind_gust_mph, temperature_f, precipitation, dome, weather_model
      FROM build_forecasts
      WHERE game_id = ${gameId}
      ORDER BY fetched_at DESC, id DESC
      LIMIT 1`;
    return rows.length ? forecastFrom(rows[0]) : null;
  } catch (e) {
    if (isMissingTable(e)) return null;
    throw e;
  }
}

/** The weather model's plain name. */
export function modelName(m: string | null): string {
  if (!m) return "Open-Meteo";
  if (m.startsWith("icon")) return "ICON";
  if (m.startsWith("gfs")) return "GFS";
  if (m.startsWith("ecmwf")) return "ECMWF";
  if (m.startsWith("gem")) return "GEM";
  if (m === "best_match") return "Open-Meteo blend";
  return m;
}

/** The factor keys the Sunday table filled; the page no longer shows them. */
export const STALE_WEATHER_KEYS = new Set(["wx_temp", "wx_wind", "wx_precip"]);

/** Wind at or above this points to less scoring (the wind strategies' line). */
export const WIND_LESS_SCORING_MPH = 10;

/**
 * The wind as a row in the factors list (Tate 2026-10-16): the steady wind at
 * kickoff from the newest card forecast, one number, no gusts; green ("points
 * to less scoring") at WIND_LESS_SCORING_MPH or more, plain below. Null indoors
 * or without a forecast.
 */
export function windFactor(f: CardForecast | null): BoardFactor | null {
  if (f === null || f.dome || f.windMph === null) return null;
  const mph = Math.round(f.windMph);
  const strong = f.windMph >= WIND_LESS_SCORING_MPH;
  return {
    key: "card_wind",
    label: "Wind",
    family: "weather",
    tier: 2,
    direction: strong ? 1 : 0,
    hypothesis: false,
    binary: false,
    value: f.windMph,
    color: strong ? "green" : "neutral",
    intensity: strong
      ? Math.min(1, 0.5 + (f.windMph - WIND_LESS_SCORING_MPH) / 20)
      : 0,
    lean: 0,
    sentence: `Wind ${mph} mph — ${strong ? "points to less scoring" : "small effect, if any"}.`,
    live: null,
  };
}
