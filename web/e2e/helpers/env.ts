// The few values the config, the setup project and the specs all share.
// Nothing here is a secret: the password never leaves the machine running
// the suite, and the database URL is the local sandbox unless CI overrides it.

export const E2E_PASSWORD = "e2e-only-not-a-secret";
export const AUTH_FILE = "e2e/.auth/user.json";
export const DEFAULT_DATABASE_URL =
  "postgresql://postgres@127.0.0.1:54329/beatvegas_e2e";

export function databaseUrl(): string {
  return process.env.DATABASE_URL ?? DEFAULT_DATABASE_URL;
}
