"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import { SourcePanel } from "@/components/SourcePanel";
import { SourceCitation, streamQuery } from "@/lib/bff";

export function ChatConsole() {
  const [question, setQuestion] = useState(
    "What competition risks are disclosed?",
  );
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<SourceCitation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setAnswer("");
    setSources([]);
    try {
      await streamQuery(question, {
        onToken: (token) => setAnswer((prev) => prev + token),
        onSources: setSources,
        onDone: (finalAnswer) => setAnswer(finalAnswer),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(16rem,0.8fr)]">
      <section>
        <h1 className="font-display text-3xl text-ink">Query console</h1>
        <p className="mt-2 text-muted">
          Streams a grounded answer from the BFF. Sources appear as citations arrive.
        </p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <label className="block text-sm font-medium text-ink" htmlFor="question">
            Question
          </label>
          <textarea
            id="question"
            className="min-h-28 w-full border border-line bg-paper px-3 py-2 text-ink outline-none ring-teal focus:ring-2"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            required
          />
          <button
            type="submit"
            disabled={busy || !question.trim()}
            className="bg-teal px-4 py-2 text-sm font-semibold text-paper disabled:opacity-50"
          >
            {busy ? "Streaming…" : "Ask"}
          </button>
        </form>
        {error ? (
          <p className="mt-4 text-sm text-amber" role="alert">
            {error}
          </p>
        ) : null}
        <article
          className="mt-8 border border-line bg-paper-deep/40 p-4 whitespace-pre-wrap"
          aria-live="polite"
        >
          {answer || (busy ? "Waiting for tokens…" : "Answer will stream here.")}
        </article>
      </section>
      <SourcePanel sources={sources} />
    </div>
  );
}
