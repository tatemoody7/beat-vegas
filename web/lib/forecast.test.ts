import { describe, expect, it } from "vitest";
import {
  forecastFrom,
  forecastLines,
  forecastSource,
  modelName,
  STALE_WEATHER_KEYS,
} from "./forecast";

// The game page's weather (Tate 2026-10-16): the newest card-build forecast,
// dated and sourced, in scoring words; the Sunday table's rows are dropped.

const row = {
  fetched_at: "2026-10-15 20:17:15.232935",
  lead_hours: 43.71,
  wind_mph: 10.9,
  wind_gust_mph: 25.1,
  temperature_f: 48.4,
  precipitation: 0,
  dome: false,
  weather_model: "icon_seamless",
};

describe("the card forecast on the game page", () => {
  it("states wind, gusts, temperature and rain in scoring words", () => {
    expect(forecastLines(forecastFrom(row))).toEqual([
      "Wind 11 mph, gusts 25 mph — points to less scoring.",
      "48°F, dry.",
    ]);
    expect(
      forecastLines(forecastFrom({ ...row, wind_mph: 6, precipitation: 0.04 })),
    ).toEqual([
      "Wind 6 mph, gusts 25 mph — small effect, if any.",
      "48°F, 0.04 in of rain in the kickoff hour.",
    ]);
  });

  it("says where and when the forecast came from", () => {
    // 20:17Z on a Thursday in October is 4:17pm ET.
    expect(forecastSource(forecastFrom(row))).toBe(
      "ICON forecast, fetched Thu 4:17pm, 44 h before kickoff",
    );
    expect(modelName("gfs_seamless")).toBe("GFS");
  });

  it("an indoor game has no weather, and the stale rows are named", () => {
    expect(forecastLines(forecastFrom({ ...row, dome: true }))).toEqual([
      "Indoors: no weather.",
    ]);
    expect([...STALE_WEATHER_KEYS].sort()).toEqual([
      "wx_precip",
      "wx_temp",
      "wx_wind",
    ]);
  });
});
