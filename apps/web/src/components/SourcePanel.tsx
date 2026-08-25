import type { SourceCitation } from "@/lib/bff";

export function SourcePanel({ sources }: { sources: SourceCitation[] }) {
  return (
    <aside className="border border-line bg-paper p-4">
      <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted">
        Sources
      </h2>
      {sources.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No citations yet.</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {sources.map((source) => (
            <li key={source.chunk_id} className="text-sm">
              <p className="font-medium text-ink">{source.section}</p>
              <p className="text-muted">{source.accession_no}</p>
              <a
                className="text-teal underline-offset-2 hover:underline"
                href={source.source_url}
                target="_blank"
                rel="noreferrer"
              >
                {source.chunk_id}
              </a>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
