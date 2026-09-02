"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Five tabs (owner-approved consolidation). The retired routes (/preview,
// /line-check, /line-study, /movement, /ledger, /weekly-review, /picks)
// redirect into these.
const LINKS = [
  { href: "/", label: "This Week" },
  { href: "/board", label: "Board" },
  { href: "/results", label: "Results" },
  { href: "/research", label: "Research" },
  { href: "/glossary", label: "Glossary" },
];

export default function MainNav() {
  const pathname = usePathname();

  return (
    <nav className="flex min-w-0 flex-1 items-end gap-6 overflow-x-clip">
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
