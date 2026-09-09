"use client";

import { usePathname } from "next/navigation";
import LogoutButton from "@/app/components/LogoutButton";
import MainNav from "@/app/components/MainNav";

// The nav tabs and the Lock button, hidden on /login: a locked-out reader has
// nothing to navigate to and nothing to lock. The wordmark stays (layout.tsx).
// Same wrapper classes and order as before, so no other page shifts.
export default function HeaderChrome({
  gateEnabled,
}: {
  gateEnabled: boolean;
}) {
  const pathname = usePathname();
  if (pathname === "/login") return null;
  return (
    <>
      <MainNav />
      {gateEnabled && (
        <div className="order-2 ml-auto shrink-0 sm:order-4">
          <LogoutButton />
        </div>
      )}
    </>
  );
}
