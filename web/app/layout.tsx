import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-gray-950 text-gray-100">
        <header className="flex items-center gap-6 border-b border-gray-800 px-6 py-3">
          <Link href="/" className="text-base font-semibold tracking-tight">
            Beat Vegas <span className="text-gray-500">— 1H Unders</span>
          </Link>
          <nav className="flex gap-4 text-sm text-gray-400">
            <Link href="/" className="hover:text-gray-100">
              Opportunities
            </Link>
            <Link href="/line-study" className="hover:text-gray-100">
              Line Study
            </Link>
            <Link href="/movement" className="hover:text-gray-100">
              Movement
            </Link>
            <Link href="/ledger" className="hover:text-gray-100">
              Ledger
            </Link>
            <Link href="/research" className="hover:text-gray-100">
              Research
            </Link>
            <Link href="/picks" className="hover:text-gray-100">
              My Picks
            </Link>
          </nav>
        </header>
        <main className="flex-1 px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
