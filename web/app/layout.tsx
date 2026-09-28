import type { Metadata } from "next";
import { Geist, Geist_Mono, Archivo } from "next/font/google";
import Link from "next/link";
import { gateEnabled } from "@/lib/auth";
import { viewerIsAuthed } from "@/lib/session";
import FooterChrome from "@/app/components/FooterChrome";
import HeaderChrome from "@/app/components/HeaderChrome";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});
const archivo = Archivo({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Beat Vegas — first-half unders",
  description:
    "College football first-half under totals. What to bet, and the numbers behind it.",
  // Readable without a password since 2026-09-16, but not for search engines:
  // every render is metered Neon egress. app/robots.ts says the same to crawlers.
  robots: { index: false, follow: false },
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Lock (signed in) or Unlock (reading publicly) in the FOOTER; the gate is
  // write-only, so this is about what the visitor can DO, not see.
  const authed = await viewerIsAuthed();
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${archivo.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl flex-nowrap items-center gap-x-2 px-4 py-3 sm:gap-x-6 sm:px-6">
            {/* ONE row at every width: wordmark and three tabs. Below `sm`
                the wordmark drops a size so 360px fits. The nav comes from
                HeaderChrome, which renders nothing on /login. */}
            <Link
              href="/"
              className="shrink-0 font-[family-name:var(--font-display)] text-sm font-extrabold tracking-tight sm:text-base"
            >
              <span className="text-[var(--accent)]">BEAT</span>
              <span className="text-[var(--text)]"> VEGAS</span>
              <span className="ml-2 hidden align-middle text-xs font-medium uppercase tracking-widest text-[var(--text-dim)] sm:inline">
                First-half unders
              </span>
            </Link>
            <HeaderChrome />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
          {children}
        </main>
        <footer className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-6 text-xs text-[var(--text-dim)]">
          <span>
            This site rates bets. It never places one. 21+. Not financial
            advice.
          </span>
          <FooterChrome gateEnabled={gateEnabled()} authed={authed} />
        </footer>
      </body>
    </html>
  );
}
