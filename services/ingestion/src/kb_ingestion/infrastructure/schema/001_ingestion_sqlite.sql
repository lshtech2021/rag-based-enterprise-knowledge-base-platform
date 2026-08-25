-- SQLite schema for local EDGAR ingest (no pgvector required)
CREATE TABLE IF NOT EXISTS companies (
    cik TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ticker TEXT,
    sic TEXT,
    last_ingested_accession TEXT
);

CREATE TABLE IF NOT EXISTS filings (
    accession_no TEXT PRIMARY KEY,
    cik TEXT NOT NULL REFERENCES companies (cik),
    form_type TEXT NOT NULL,
    filed_date TEXT NOT NULL,
    period TEXT,
    s3_raw_path TEXT NOT NULL,
    source_url TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    accession_no TEXT NOT NULL REFERENCES filings (accession_no),
    section TEXT NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id TEXT PRIMARY KEY REFERENCES chunks (chunk_id),
    embedding_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS filings_cik_idx ON filings (cik);
CREATE INDEX IF NOT EXISTS chunks_accession_idx ON chunks (accession_no);
