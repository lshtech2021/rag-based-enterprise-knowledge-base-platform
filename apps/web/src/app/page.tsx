import Link from "next/link";

export default function HomePage() {
  return (
    <section className="atmosphere relative min-h-[calc(100vh-4rem)] overflow-hidden">
      <div className="grid-fade pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl flex-col justify-center px-6 py-16">
        <p className="font-display text-5xl tracking-tight text-ink sm:text-7xl md:text-8xl">
          Annex
        </p>
        <h1 className="mt-6 max-w-2xl text-2xl leading-snug text-ink sm:text-3xl">
          Filing knowledge you can cite.
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted">
          Ask grounded questions over SEC disclosures and assemble reports that keep every
          claim tied to its source.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <Link
            href="/console"
            className="bg-ink px-5 py-3 text-sm font-semibold tracking-wide text-paper transition hover:bg-teal"
          >
            Open console
          </Link>
          <Link
            href="/reports"
            className="border border-ink/20 bg-paper/70 px-5 py-3 text-sm font-semibold tracking-wide text-ink transition hover:border-teal hover:text-teal"
          >
            Build a report
          </Link>
        </div>
      </div>
    </section>
  );
}
