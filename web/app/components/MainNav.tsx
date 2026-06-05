"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Opportunities" },
  { href: "/line-check", label: "Line Check" },
  { href: "/line-study", label: "Line Study" },
  { href: "/movement", label: "Movement" },
  { href: "/ledger", label: "Ledger" },
  { href: "/research", label: "Research" },
  { href: "/picks", label: "My Picks" },
];

export default function MainNav() {
  const pathname = usePathname();

  return (
    <nav className="flex min-w-0 flex-1 gap-6 overflow-x-auto">
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
