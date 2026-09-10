import Image from "next/image";
import { logoSrc } from "@/lib/teamLogos";

// A team's mark, immediately left of its name on the board row and the game
// page header. Decorative: the name is right there, so it carries no alt text.
//
// When there is no artwork for the team (FCS and NAIA opponents, mostly) this
// renders NOTHING — no blank circle, no initials, no reserved box (Tate,
// 2026-09-10). The name simply starts where it would have anyway.
//
// No backplate and no ring: colour on this site is the grade language
// (globals.css), and a chrome frame around a logo would read as one. `unoptimized`
// because the files are already the exact size they render at — there is nothing
// for Vercel's image pipeline to do but bill for it.

export default function TeamLogo({ teamId }: { teamId: number | null }) {
  const src = logoSrc(teamId);
  if (src === null) return null;
  return (
    <Image
      className="bv-team-logo"
      src={src}
      alt=""
      aria-hidden
      width={18}
      height={18}
      unoptimized
    />
  );
}
