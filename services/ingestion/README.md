# Ingestion service

EDGAR ETL: fetch → store → parse → chunk → embed.

Spec: [`SPEC-ingestion.md`](../../SPEC-ingestion.md)

```bash
uv run pytest services/ingestion -q
# Optional UI (when exploring assets):
# uv run dagster dev -f services/ingestion/src/kb_ingestion/presentation/definitions.py
```

Layers: `application` / `domain` / `infrastructure` / `presentation`.
