import pg from "pg";
import { databaseUrl } from "./env";

// Direct SQL against the FIXTURE database, for the few specs that have to put
// the app into a state the clean seed never shows (an Odds API budget near
// zero, the real-money pause). Same refusal as seed.mjs: never Neon.

export function refuseNeon(url: string): void {
  if (/neon\.tech/i.test(url)) {
    throw new Error("e2e helpers never touch a neon.tech database");
  }
}

export async function query<T extends pg.QueryResultRow = pg.QueryResultRow>(
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const url = databaseUrl();
  refuseNeon(url);
  const client = new pg.Client({ connectionString: url });
  await client.connect();
  try {
    const res = await client.query<T>(sql, params);
    return res.rows;
  } finally {
    await client.end();
  }
}

/** Set one app_settings gauge (upsert) and return what it was, for `finally`. */
export async function setSetting(
  key: string,
  value: string,
): Promise<string | null> {
  const before = await query<{ value: string }>(
    "SELECT value FROM app_settings WHERE key = $1",
    [key],
  );
  await query(
    `INSERT INTO app_settings (key, value, updated_at)
     VALUES ($1, $2, (now() AT TIME ZONE 'utc'))
     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at`,
    [key, value],
  );
  return before[0]?.value ?? null;
}

/** Put a gauge back exactly as it was (deleting it if it did not exist). */
export async function restoreSetting(
  key: string,
  previous: string | null,
): Promise<void> {
  if (previous === null) {
    await query("DELETE FROM app_settings WHERE key = $1", [key]);
  } else {
    await setSetting(key, previous);
  }
}
