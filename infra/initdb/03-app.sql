-- Architecture §7 tables beyond the core ingestion set (02-ingestion.sql).
-- These are also applied idempotently by the app on connect (see
-- kb_ingestion PostgresKnowledgeStore.connect / kb_report
-- PostgresReportRepository.connect) so a pre-existing Postgres (not only a
-- fresh Compose volume) ends up with the same schema.

CREATE TABLE IF NOT EXISTS financial_facts (
    cik VARCHAR(10) NOT NULL REFERENCES companies (cik),
    concept TEXT NOT NULL,
    unit TEXT NOT NULL,
    value NUMERIC NOT NULL,
    fiscal_period TEXT NOT NULL,
    accession_no VARCHAR(20) NOT NULL REFERENCES filings (accession_no),
    PRIMARY KEY (cik, concept, unit, fiscal_period, accession_no)
);

CREATE INDEX IF NOT EXISTS financial_facts_cik_idx ON financial_facts (cik);

CREATE TABLE IF NOT EXISTS query_logs (
    query_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    question TEXT NOT NULL,
    retrieved_chunks JSONB NOT NULL DEFAULT '[]'::jsonb,
    answer TEXT NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS query_logs_user_idx ON query_logs (user_id);

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
