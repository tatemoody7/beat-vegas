"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import LogoutButton from "@/app/components/LogoutButton";
import MainNav from "@/app/components/MainNav";

// The nav tabs and the Lock / Unlock control, hidden on /login: a reader on the
// login form has nothing to navigate to. The wordmark stays (layout.tsx).
//
// The site reads publicly (2026-09-16); the password guards logging picks. So
// a signed-in visitor sees Lock (drop the cookie) and everyone else sees
// Unlock, which is the way to the log-pick form.
export default function HeaderChrome({
  gateEnabled,
  authed,
}: {
  gateEnabled: boolean;
  authed: boolean;
}) {
  const pathname = usePathname();
  if (pathname === "/login") return null;
  return (
    <>
      <MainNav />
      {gateEnabled && (
        <div className="order-2 ml-auto shrink-0 sm:order-4">
          {authed ? <LogoutButton /> : <UnlockLink />}
        </div>
      )}
    </>
  );
}

function UnlockLink() {
  return (
    <Link
      href="/login"
      aria-label="Unlock"
      className="bv-btn bv-btn--ghost shrink-0 px-2 py-1.5 text-xs font-semibold uppercase tracking-wide sm:px-3"
    >
      {/* Same shape as Lock: the word at sm+, an open padlock below it. */}
      <span className="hidden sm:inline">Unlock</span>
      <svg
        aria-hidden
        className="h-3.5 w-3.5 sm:hidden"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        <rect x="3" y="7" width="10" height="7" rx="1.5" />
        <path d="M5 7V5a3 3 0 0 1 6 0" />
      </svg>
    </Link>
  );
}
