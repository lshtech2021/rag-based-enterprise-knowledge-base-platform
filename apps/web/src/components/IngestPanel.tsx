"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import {
  createIngest,
  downloadFilingRaw,
  type IngestResponse,
} from "@/lib/bff";

const FORM_OPTIONS = ["10-K", "10-Q", "8-K"] as const;

export function IngestPanel() {
  const [cik, setCik] = useState("320193");
  const [forms, setForms] = useState<string[]>(["10-K", "10-Q", "8-K"]);
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);

  function toggleForm(form: string) {
    setForms((current) =>
      current.includes(form)
        ? current.filter((entry) => entry !== form)
        : [...current, form],
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (forms.length === 0) {
      setError("Select at least one document type");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createIngest({
        cik: cik.trim(),
        form_types: forms,
        force,
      });
      setResult(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDownload() {
    if (!result) return;
    setDownloading(true);
    setError(null);
    try {
      const blob = await downloadFilingRaw(result.accession_no);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${result.accession_no}.htm`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-3xl text-ink">Ingest filings</h1>
        <p className="mt-2 text-muted">
          Pull the latest EDGAR filing for a CIK, chunk and embed it into the knowledge
          base, then download the raw HTML.
        </p>
      </div>
      <form className="grid gap-4" onSubmit={onSubmit}>
        <label className="block text-sm font-medium">
          CIK
          <input
            className="mt-1 w-full border border-line bg-paper px-3 py-2 outline-none ring-teal focus:ring-2"
            value={cik}
            onChange={(event) => setCik(event.target.value)}
            placeholder="320193"
            required
          />
        </label>
        <fieldset>
          <legend className="text-sm font-medium">Document types</legend>
          <div className="mt-2 flex flex-wrap gap-4">
            {FORM_OPTIONS.map((form) => (
              <label key={form} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={forms.includes(form)}
                  onChange={() => toggleForm(form)}
                />
                {form}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={force}
            onChange={(event) => setForce(event.target.checked)}
          />
          Force re-ingest
        </label>
        <div>
          <button
            type="submit"
            disabled={busy}
            className="bg-ink px-4 py-2 text-sm font-semibold text-paper disabled:opacity-50"
          >
            {busy ? "Ingesting…" : "Ingest"}
          </button>
        </div>
      </form>
      {error ? (
        <p className="text-sm text-amber" role="alert">
          {error}
        </p>
      ) : null}
      {result ? (
        <section className="space-y-4 border border-line bg-paper-deep/30 p-5">
          <div>
            <h2 className="font-display text-2xl">
              {result.skipped ? "Already ingested" : "Ingested"}
            </h2>
            <p className="text-sm text-muted">
              Accession {result.accession_no} · {result.chunk_count} chunks
            </p>
          </div>
          <button
            type="button"
            onClick={onDownload}
            disabled={downloading}
            className="border border-ink px-4 py-2 text-sm font-semibold text-ink disabled:opacity-50"
          >
            {downloading ? "Downloading…" : "Download filing"}
          </button>
        </section>
      ) : null}
    </div>
  );
}
