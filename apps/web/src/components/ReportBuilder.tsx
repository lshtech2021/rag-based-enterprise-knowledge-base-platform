"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import { createReport, type ReportResponse } from "@/lib/bff";
import { MarkdownContent } from "@/components/MarkdownContent";

export function ReportBuilder() {
  const [company, setCompany] = useState("Apple Inc.");
  const [period, setPeriod] = useState("FY2024");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createReport({ company, period });
      setReport(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-3xl text-ink">Report builder</h1>
        <p className="mt-2 text-muted">
          Runs the quarterly risk summary template through grounded section queries.
        </p>
      </div>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={onSubmit}>
        <label className="block text-sm font-medium">
          Company
          <input
            className="mt-1 w-full border border-line bg-paper px-3 py-2 outline-none ring-teal focus:ring-2"
            value={company}
            onChange={(event) => setCompany(event.target.value)}
            required
          />
        </label>
        <label className="block text-sm font-medium">
          Period
          <input
            className="mt-1 w-full border border-line bg-paper px-3 py-2 outline-none ring-teal focus:ring-2"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
            required
          />
        </label>
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={busy}
            className="bg-ink px-4 py-2 text-sm font-semibold text-paper disabled:opacity-50"
          >
            {busy ? "Generating…" : "Generate report"}
          </button>
        </div>
      </form>
      {error ? (
        <p className="text-sm text-amber" role="alert">
          {error}
        </p>
      ) : null}
      {report ? (
        <section className="space-y-4 border border-line bg-paper-deep/30 p-5">
          <p className="text-sm text-muted">Report ID · {report.report_id}</p>
          <MarkdownContent markdown={report.markdown} />
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">
              Citations
            </h3>
            <ul className="mt-2 space-y-2 text-sm">
              {report.citations.map((cite) => (
                <li key={`${cite.section_id}-${cite.chunk_id}`}>
                  <span className="font-medium">{cite.section_id}</span>: {cite.chunk_id} —{" "}
                  {cite.section}
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </div>
  );
}
