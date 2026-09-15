import { describe, expect, it } from "vitest";
import { isMissingTable, rulePauseFrom, utcFrom } from "./rulePause";

describe("rulePauseFrom", () => {
  it("no row is not paused — an absent switch was never thrown", () => {
    expect(rulePauseFrom([])).toEqual({ paused: false });
  });

  it("only the exact string 'true' pauses", () => {
    expect(
      rulePauseFrom([{ value: "false", note: null, updated_at: null }]),
    ).toEqual({ paused: false });
    expect(
      rulePauseFrom([{ value: "TRUE", note: null, updated_at: null }]),
    ).toEqual({ paused: false });
    expect(
      rulePauseFrom([{ value: "1", note: null, updated_at: null }]),
    ).toEqual({ paused: false });
    expect(
      rulePauseFrom([{ value: " true ", note: null, updated_at: null }]),
    ).toMatchObject({ paused: true });
  });

  it("carries the note and a UTC since", () => {
    const r = rulePauseFrom([
      {
        value: "true",
        note: "  week 6 boundary ",
        updated_at: "2026-10-12T14:05:00",
      },
    ]);
    expect(r).toMatchObject({ paused: true, note: "week 6 boundary" });
    expect((r as { since: Date }).since.toISOString()).toBe(
      "2026-10-12T14:05:00.000Z",
    );
  });

  it("reads an empty note as null", () => {
    expect(
      rulePauseFrom([{ value: "true", note: "  ", updated_at: null }]),
    ).toMatchObject({ paused: true, note: null, since: null });
  });
});

describe("isMissingTable", () => {
  it("matches the Postgres and SQLite messages and not a connection error", () => {
    expect(
      isMissingTable(new Error('relation "app_settings" does not exist')),
    ).toBe(true);
    expect(isMissingTable(new Error("no such table: app_settings"))).toBe(true);
    expect(isMissingTable(new Error("connection timeout expired"))).toBe(false);
  });
});

describe("utcFrom", () => {
  it("treats the naive text as UTC and rejects garbage", () => {
    expect(utcFrom("2026-09-15T20:00:00")?.toISOString()).toBe(
      "2026-09-15T20:00:00.000Z",
    );
    expect(utcFrom(null)).toBeNull();
    expect(utcFrom("not a date")).toBeNull();
  });
});
