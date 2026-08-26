-- Ingestion schema (Postgres 16 + pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS companies (
    cik VARCHAR(10) PRIMARY KEY,
    name TEXT NOT NULL,
    ticker TEXT,
    sic TEXT,
    last_ingested_accession VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS filings (
    accession_no VARCHAR(20) PRIMARY KEY,
    cik VARCHAR(10) NOT NULL REFERENCES companies (cik),
    form_type TEXT NOT NULL,
    filed_date DATE NOT NULL,
    period TEXT,
    s3_raw_path TEXT NOT NULL,
    source_url TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    accession_no VARCHAR(20) NOT NULL REFERENCES filings (accession_no),
    section TEXT NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id TEXT PRIMARY KEY REFERENCES chunks (chunk_id) ON DELETE CASCADE,
    embedding vector(1536) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS filings_cik_idx ON filings (cik);
CREATE INDEX IF NOT EXISTS chunks_accession_idx ON chunks (accession_no);
CREATE INDEX IF NOT EXISTS embeddings_hnsw_idx
    ON embeddings USING hnsw (embedding vector_cosine_ops);
