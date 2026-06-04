import type { Metadata } from "next";
import { Geist, Geist_Mono, Archivo } from "next/font/google";
import Link from "next/link";
import { gateEnabled } from "@/lib/auth";
import LogoutButton from "@/app/components/LogoutButton";
import MainNav from "@/app/components/MainNav";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const archivo = Archivo({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Beat Vegas — 1H Unders",
  description: "College football first-half unders research board.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${archivo.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <header className="sticky top-0 z-40 border-b border-[var(--border-soft)] bg-[var(--bg)]/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-3">
            <Link
              href="/"
              className="shrink-0 font-[family-name:var(--font-display)] text-base font-extrabold tracking-tight"
            >
              <span className="text-[var(--accent)]">BEAT</span>
              <span className="text-[var(--text)]"> VEGAS</span>
              <span className="ml-2 hidden align-middle text-xs font-medium uppercase tracking-widest text-[var(--text-dim)] sm:inline">
                1H Unders
              </span>
            </Link>
            <MainNav />
            {gateEnabled() && (
              <div className="ml-auto shrink-0">
                <LogoutButton />
              </div>
            )}
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
