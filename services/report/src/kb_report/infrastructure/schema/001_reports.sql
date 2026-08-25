-- Report persistence (Postgres) — apply when Compose DB is available
CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    template TEXT NOT NULL,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    markdown TEXT NOT NULL,
    s3_output_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS report_citations (
    report_id TEXT NOT NULL REFERENCES reports (report_id),
    section_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    accession_no TEXT NOT NULL,
    section TEXT NOT NULL,
    source_url TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS report_citations_report_idx ON report_citations (report_id);
