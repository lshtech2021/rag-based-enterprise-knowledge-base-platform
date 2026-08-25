import type { Metadata } from "next";
import { Literata, Source_Sans_3 } from "next/font/google";

import { AppChrome } from "@/components/AppChrome";

import "./globals.css";

const literata = Literata({
  variable: "--font-literata",
  subsets: ["latin"],
  display: "swap",
});

const sourceSans = Source_Sans_3({
  variable: "--font-source-sans",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Annex — Filing knowledge with provenance",
  description: "Ask grounded questions and generate citation-backed reports from SEC filings.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${literata.variable} ${sourceSans.variable} antialiased`}>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}
