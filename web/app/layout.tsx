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
        <header className="border-b border-gray-800 px-6 py-3">
          <Link href="/" className="text-base font-semibold tracking-tight">
            Beat Vegas <span className="text-gray-500">— 1H Unders</span>
          </Link>
        </header>
        <main className="flex-1 px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
