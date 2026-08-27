"use client";

import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { MarkdownContent } from "@/components/MarkdownContent";
import {
  streamQuery,
  type ChatHistoryMessage,
  type SourceCitation,
} from "@/lib/bff";

type ChatTurn = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceCitation[];
};

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ChatThread() {
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  function clearChat() {
    if (busy) return;
    setMessages([]);
    setError(null);
    setDraft("");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || busy) return;

    const history: ChatHistoryMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    const userTurn: ChatTurn = { id: newId(), role: "user", content: question };
    const assistantId = newId();

    setDraft("");
    setError(null);
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      userTurn,
      { id: assistantId, role: "assistant", content: "" },
    ]);

    let sources: SourceCitation[] = [];
    try {
      await streamQuery(
        question,
        {
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + token } : m,
              ),
            );
          },
          onSources: (next) => {
            sources = next;
          },
          onDone: (finalAnswer) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: finalAnswer, sources }
                  : m,
              ),
            );
          },
        },
        { history },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
      setMessages((prev) =>
        prev.filter((m) => m.id !== assistantId && m.id !== userTurn.id),
      );
      setDraft(question);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-[70vh] flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl text-ink">Chat</h1>
          <p className="mt-2 text-muted">
            Multi-turn grounded Q&amp;A. Follow-ups use prior turns for rewrite and
            generation.
          </p>
        </div>
        <button
          type="button"
          onClick={clearChat}
          disabled={busy || messages.length === 0}
          className="border border-line px-3 py-2 text-sm font-medium text-muted hover:text-ink disabled:opacity-50"
        >
          New chat
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col border border-line bg-paper-deep/30">
        <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
          {messages.length === 0 ? (
            <p className="text-sm text-muted">
              Ask a question about ingested filings. Sources appear under each
              answer.
            </p>
          ) : null}
          {messages.map((message) => (
            <div
              key={message.id}
              className={
                message.role === "user"
                  ? "ml-8 border border-line bg-paper p-3"
                  : "mr-8 border border-line bg-paper-deep/60 p-3"
              }
            >
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                {message.role === "user" ? "You" : "Annex"}
              </p>
              {message.role === "assistant" ? (
                message.content ? (
                  <MarkdownContent markdown={message.content} />
                ) : (
                  <p className="text-sm text-muted">
                    {busy ? "Waiting for tokens…" : ""}
                  </p>
                )
              ) : (
                <p className="whitespace-pre-wrap text-sm text-ink">{message.content}</p>
              )}
              {message.role === "assistant" && message.sources?.length ? (
                <ul className="mt-3 space-y-1 border-t border-line pt-3 text-xs text-muted">
                  {message.sources.map((source) => (
                    <li key={`${message.id}-${source.chunk_id}`}>
                      <a
                        className="text-teal underline-offset-2 hover:underline"
                        href={source.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {source.chunk_id}
                      </a>
                      {" — "}
                      {source.section}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form
          className="border-t border-line bg-paper p-4"
          onSubmit={onSubmit}
        >
          {error ? (
            <p className="mb-3 text-sm text-amber" role="alert">
              {error}
            </p>
          ) : null}
          <label className="sr-only" htmlFor="chat-draft">
            Message
          </label>
          <textarea
            id="chat-draft"
            className="min-h-24 w-full border border-line bg-paper px-3 py-2 text-ink outline-none ring-teal focus:ring-2"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask a follow-up…"
            disabled={busy}
            required
          />
          <div className="mt-3 flex justify-end">
            <button
              type="submit"
              disabled={busy || !draft.trim()}
              className="bg-teal px-4 py-2 text-sm font-semibold text-paper disabled:opacity-50"
            >
              {busy ? "Streaming…" : "Send"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
