"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Three tabs, one job each: scan the week, see the record, follow the research.
// The retired routes (/board, /preview, /line-check, /line-study, /movement,
// /ledger, /weekly-review, /picks, /how-it-works, /proof, /glossary) redirect
// into these. /records (every game rated) lights no tab; it is reached from
// Research and Results.
const LINKS = [
  { href: "/", label: "Board" },
  { href: "/results", label: "Results" },
  { href: "/research", label: "Research" },
];

export default function MainNav() {
  const pathname = usePathname();

  return (
    <nav className="flex min-w-0 flex-1 flex-nowrap items-center gap-x-3 sm:gap-x-5">
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
