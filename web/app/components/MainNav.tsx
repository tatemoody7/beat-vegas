"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// The board is the home page; the retired routes (/board, /preview,
// /line-check, /line-study, /movement, /ledger, /weekly-review, /picks)
// redirect into these.
const LINKS = [
  { href: "/", label: "Board" },
  { href: "/slip", label: "Bet slip" },
  { href: "/results", label: "Results" },
  { href: "/research", label: "Research" },
  { href: "/glossary", label: "Glossary" },
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
