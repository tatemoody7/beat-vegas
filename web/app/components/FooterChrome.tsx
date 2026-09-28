"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import LogoutButton from "@/app/components/LogoutButton";

// The footer's right-hand side: the way in for the password holder, or the way
// out. The site reads publicly (2026-09-16); the password guards logging picks
// only, so the control is a footnote, not a header button (2026-09-28).
export default function FooterChrome({
  gateEnabled,
  authed,
}: {
  gateEnabled: boolean;
  authed: boolean;
}) {
  const pathname = usePathname();
  if (!gateEnabled || pathname === "/login") return null;
  return authed ? (
    <span className="inline-flex items-center gap-1.5">
      <span>Signed in ·</span>
      <LogoutButton />
    </span>
  ) : (
    <Link
      href="/login"
      aria-label="Unlock"
      className="inline-flex min-h-6 items-center underline underline-offset-2 hover:text-[var(--text)]"
    >
      Unlock
    </Link>
  );
}
