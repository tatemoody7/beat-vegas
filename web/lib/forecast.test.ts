import { describe, expect, it } from "vitest";
import {
  forecastFrom,
  modelName,
  STALE_WEATHER_KEYS,
  windFactor,
} from "./forecast";

// The wind row in the factors list (Tate 2026-10-16): the steady wind from the
// newest card forecast, one number, green at 10+ mph, plain below.

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

describe("the wind row", () => {
  it("is green at 10 mph or more and names the steady wind only", () => {
    const w = windFactor(forecastFrom(row))!;
    expect(w.sentence).toBe("Wind 11 mph — points to less scoring.");
    expect(w.color).toBe("green");
    expect(w.sentence).not.toMatch(/gust/);
  });

  it("is plain below 10 mph", () => {
    const w = windFactor(forecastFrom({ ...row, wind_mph: 4.2 }))!;
    expect(w.sentence).toBe("Wind 4 mph — small effect, if any.");
    expect(w.color).toBe("neutral");
  });

  it("is absent indoors or without a forecast", () => {
    expect(windFactor(forecastFrom({ ...row, dome: true }))).toBeNull();
    expect(windFactor(null)).toBeNull();
    expect(modelName("icon_seamless")).toBe("ICON");
    expect([...STALE_WEATHER_KEYS].sort()).toEqual([
      "wx_precip",
      "wx_temp",
      "wx_wind",
    ]);
  });
});
