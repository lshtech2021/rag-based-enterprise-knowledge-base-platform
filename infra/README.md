# Local data plane

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps
```

| Service | Port | Notes |
|---|---|---|
| Postgres + pgvector | 5432 | user/pass/db: `kb` / `kb` / `knowledge_base`; `vector` extension via `initdb/` |
| Redis | 6379 | cache + Redis Streams |
| MinIO | 9000 (API), 9001 (console) | `minioadmin` / `minioadmin` |
| OpenSearch | 9200 | optional: `docker compose -f infra/docker-compose.yml --profile opensearch up -d` |

Default app auth for local BFF: `AUTH_MODE=dev_bypass` (see repo `.env.example`).
