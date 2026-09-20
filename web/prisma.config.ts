// Prisma 7 moved the datasource URL out of schema.prisma and into this file.
//
// The URL here is for the CLI only (migrate / db pull / studio). The running app
// never reads it: since Prisma 7 every client carries a driver adapter, and the
// adapter in lib/prisma.ts takes DATABASE_URL from the environment itself. So a
// missing variable must not break `prisma generate`, which postinstall and
// `npm run build` run on CI and on Vercel with no database in scope -- hence the
// placeholder rather than Prisma's `env()` helper, which throws at config load.
// dotenv is loaded because Prisma 7 no longer reads .env itself (web/.env holds
// the local URL; see .env.example).
import "dotenv/config";
import { defineConfig } from "prisma/config";

export default defineConfig({
  schema: "prisma/schema.prisma",
  datasource: {
    url:
      process.env.DATABASE_URL ??
      "postgresql://unset:unset@localhost:5432/unset?schema=public",
  },
});
