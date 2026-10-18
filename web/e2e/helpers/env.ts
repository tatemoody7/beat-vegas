// The few values the config, the setup project and the specs all share.
// Nothing here is a secret: the database URL is the local sandbox unless CI
// overrides it. There is no password any more (2026-10-18, D17): the site is
// a read-only record and the e2e lane signs nobody in.

export const DEFAULT_DATABASE_URL =
  "postgresql://postgres@127.0.0.1:54329/beatvegas_e2e";

export function databaseUrl(): string {
  return process.env.DATABASE_URL ?? DEFAULT_DATABASE_URL;
}
