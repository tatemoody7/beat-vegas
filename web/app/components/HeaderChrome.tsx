"use client";

import { usePathname } from "next/navigation";
import MainNav from "@/app/components/MainNav";

// The nav tabs, hidden on /login: a reader on the login form has nothing to
// navigate to. The wordmark stays (layout.tsx). Lock / Unlock left the header
// for the footer on 2026-09-28 (site review): a visitor never sees a lock they
// cannot open, and the one-row phone header stops fighting a fourth control.
export default function HeaderChrome() {
  const pathname = usePathname();
  if (pathname === "/login") return null;
  return <MainNav />;
}
