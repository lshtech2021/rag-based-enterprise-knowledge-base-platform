# Spec: frontend

Module id: `frontend`  
Depends on: `identity`, `query`, `report`  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)

---

## Objective

Give analysts a branded web UI to **ask grounded questions** (SSE + source panel), **ingest EDGAR filings** (CIK + form types + raw download), and **generate citation-backed reports**, talking to the BFF under `dev_bypass` by default.

**Brand:** **Annex** — enterprise filing knowledge with provenance first.

**MVP success:**  
- Landing with strong Annex brand signal  
- `/console` streams `POST /v1/query` SSE (`token` / `sources` / `done`) and shows sources  
- `/ingest` runs `POST /v1/ingest` and offers `GET /v1/filings/{accession}/raw` download  
- `/reports` creates a `quarterly_risk_summary` report and renders returned Markdown + citations  
- `GET /v1/me` shown in chrome  
- Responsive; keyboard-accessible controls; BFF CORS enabled for local Next origin  

---

## Tech Stack

| Piece | Choice |
|---|---|
| App | Next.js 15 App Router in `apps/web` |
| Styling | Tailwind CSS + CSS variables (teal/slate/ink — not purple) |
| Fonts | `next/font`: Literata (display) + Source Sans 3 (UI) |
| API | `NEXT_PUBLIC_BFF_URL` (default `http://localhost:8000`) |
| Auth UI | Dev bypass — no login form; show principal from `/v1/me` |

---

## Commands

```bash
cd apps/web && npm install && npm run dev
cd apps/web && npm run lint && npm run build
# BFF (separate terminal):
uv run uvicorn kb_bff.main:app --reload --port 8000
```

---

## Project Structure

```
apps/web/
  src/app/           # layout, page, console, ingest, reports
  src/components/    # ChatConsole, IngestPanel, ReportBuilder, AppChrome
  src/lib/bff.ts     # fetch helpers + SSE parser + ingest/download
```

---

## Testing Strategy

- `npm run build` as the primary gate (typecheck + compile)
- `npm run lint`
- Manual: console SSE + report create against BFF with fakes/configured state

---

## Boundaries

**Always:** Cite sources in UI; don’t invent client-side answers without BFF; keep brand visible on first viewport of marketing/landing.

**Ask first:** Adding Auth0/Keycloak login UI; shadcn wholesale redesign.

**Never:** Commit `.env.local` with secrets; call OpenAI from the browser.

---

## Success Criteria

1. `npm run build` succeeds in `apps/web`.
2. Landing first viewport: brand **Annex**, one headline, one supporting line, CTA to console.
3. Console streams tokens and lists sources from SSE.
4. Ingest page accepts CIK + form types, shows accession/chunk count, and downloads raw HTML.
5. Reports page can POST template + company/period and show markdown.
6. BFF allows CORS from `http://localhost:3000`.
7. Capability map / SPEC index updated.

---

## Open Questions

None for MVP. Real SSO UI waits on production OIDC choice.
