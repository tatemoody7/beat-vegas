import type { MetadataRoute } from "next";

// The site is readable without a password (2026-09-16) so friends can open
// the link. It is not meant to be indexed: every render is metered Neon
// egress, and a crawler walking 64 game pages is a bill, not a reader.
export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", disallow: "/" } };
}
