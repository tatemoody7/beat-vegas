"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Three tabs, one job each: scan the week, see the money, check the evidence.
// The retired routes (/board, /preview, /line-check, /line-study, /movement,
// /ledger, /weekly-review, /picks, /research, /glossary) redirect into these.
//
// `startsWith` is what makes /proof/records light up Track record.
const LINKS = [
  { href: "/", label: "Board" },
  { href: "/results", label: "Results" },
  { href: "/proof", label: "Track record" },
];

export default function MainNav() {
  const pathname = usePathname();

  return (
    <nav className="order-3 flex w-full flex-nowrap items-end gap-x-4 gap-y-1 sm:w-auto sm:min-w-0 sm:flex-1 sm:gap-x-5">
      {LINKS.map((l) => {
        const active =
          l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            data-active={active}
            aria-current={active ? "page" : undefined}
            className="bv-nav-link"
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
