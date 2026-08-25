"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchMe, type MeResponse } from "@/lib/bff";

export function AppChrome({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<MeResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((value) => {
        if (!cancelled) setMe(value);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-paper/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
          <Link href="/" className="font-display text-2xl tracking-tight text-ink">
            Annex
          </Link>
          <nav className="flex items-center gap-5 text-sm font-medium text-muted">
            <Link className="hover:text-teal" href="/console">
              Console
            </Link>
            <Link className="hover:text-teal" href="/ingest">
              Ingest
            </Link>
            <Link className="hover:text-teal" href="/reports">
              Reports
            </Link>
            <span className="hidden text-xs sm:inline" aria-live="polite">
              {me
                ? `${me.user_id} · ${me.auth_mode}`
                : "BFF offline"}
            </span>
          </nav>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
