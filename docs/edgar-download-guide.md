# Guide: Downloading SEC EDGAR Data

Practical guide for fetching company filings from the U.S. Securities and Exchange Commission (SEC) EDGAR system. It aligns with this platform’s ingestion design ([architecture-design.md](architecture-design.md)) and the `HttpEdgarClient` in `services/ingestion`.

EDGAR data is **public**. Still follow SEC fair-access rules: identify yourself and throttle requests.

---

## 1. Before you download

### Required `User-Agent`

SEC expects a descriptive User-Agent that includes a contact email, for example:

```http
User-Agent: Annex Knowledge Base research@example.com
```

Requests without a proper User-Agent are often blocked or throttled aggressively.

### Rate limit

Stay at or below **10 requests per second** to SEC hosts (`data.sec.gov`, `www.sec.gov`). This repo’s client uses a sliding-window limiter at that budget.

### CIK (Central Index Key)

Filings are keyed by **CIK**, a numeric company id, usually stored **zero-padded to 10 digits**:

| Company (example) | Raw CIK | Padded CIK |
|---|---|---|
| Apple Inc. | 320193 | `0000320193` |

Useful lookups:

- Company search / ticker tools on [sec.gov](https://www.sec.gov)
- Submissions JSON (below) includes `name`, `tickers`, and filing history once you know the CIK

In this codebase, `CIK` normalization lives in `packages/domain` (`kb_domain.CIK`).

---

## 2. Main download surfaces

| Purpose | URL pattern |
|---|---|
| Company submission index | `https://data.sec.gov/submissions/CIK##########.json` |
| Raw filing document | `https://www.sec.gov/Archives/edgar/data/{cik_no_pad}/{accession_no_dashes}/{primary_document}` |
| Structured XBRL company facts | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` |
| XBRL frames (concept across filers) | `https://data.sec.gov/api/xbrl/frames/...` (advanced) |

`##########` = 10-digit zero-padded CIK.

---

## 3. Step-by-step: one company’s latest 10-K

### Step A — Fetch the submissions index

```bash
CIK=0000320193
curl -sS \
  -H "User-Agent: Annex Knowledge Base research@example.com" \
  -H "Accept-Encoding: gzip, deflate" \
  "https://data.sec.gov/submissions/CIK${CIK}.json" \
  -o "submissions-${CIK}.json"
```

Important fields under `filings.recent` (parallel arrays):

- `form` — e.g. `10-K`, `10-Q`, `8-K`
- `accessionNumber` — e.g. `0000320193-24-000123`
- `filingDate` — ISO date
- `primaryDocument` — main HTML/XML file name

Company display name is usually at the top-level `name` field.

### Step B — Build the archive URL

1. Pick a row where `form` is the type you want (e.g. `10-K`).
2. Take `accessionNumber`, **remove hyphens** → accession path.
3. Use the **unpadded** numeric CIK in the archive path (`int(CIK)` → `320193` for Apple).
4. Append `primaryDocument`.

Example:

```text
accessionNumber = 0000320193-24-000123
accession_path  = 000032019324000123
cik_numeric     = 320193
primaryDocument = aapl-20240928.htm

URL =
https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm
```

### Step C — Download the primary document

```bash
curl -sS \
  -H "User-Agent: Annex Knowledge Base research@example.com" \
  -H "Accept-Encoding: gzip, deflate" \
  "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm" \
  -o aapl-10k.htm
```

Save the raw bytes immutably (this platform targets MinIO/S3 plus a `filings` metadata row).

### Step D — (Optional) Download XBRL company facts

```bash
curl -sS \
  -H "User-Agent: Annex Knowledge Base research@example.com" \
  "https://data.sec.gov/api/xbrl/companyfacts/CIK${CIK}.json" \
  -o "companyfacts-${CIK}.json"
```

Use this for structured `financial_facts`; HTML/primary docs remain the main RAG text path in the MVP.

---

## 4. Minimal Python example (httpx)

```python
import httpx

USER_AGENT = "Annex Knowledge Base research@example.com"
CIK = "0000320193"

headers = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}

with httpx.Client(timeout=30.0, headers=headers) as client:
    submissions = client.get(
        f"https://data.sec.gov/submissions/CIK{CIK}.json"
    ).json()

    recent = submissions["filings"]["recent"]
    idx = next(i for i, form in enumerate(recent["form"]) if form == "10-K")

    accession = recent["accessionNumber"][idx]
    primary = recent["primaryDocument"][idx]
    accession_path = accession.replace("-", "")
    cik_num = int(CIK)

    url = (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_num}/{accession_path}/{primary}"
    )
    html = client.get(url).content
    open(primary, "wb").write(html)
    print("saved", primary, "from", url)
```

Prefer async + an explicit rate limiter in production (see `HttpEdgarClient` / `RateLimiter` in `services/ingestion`).

---

## 5. Incremental / curated downloads

Do **not** scrape “all of EDGAR” on day one.

Recommended pattern (also used by this platform):

1. Maintain a curated CIK list (tickers/companies you care about).
2. For each CIK, read submissions JSON.
3. Track `last_ingested_accession` (or last filing date) per CIK.
4. Download only accessions newer than that cursor.
5. Persist raw files under a stable key, e.g.  
   `filings/{cik}/{accession}/{primary_document}`

Form filter for MVP: `10-K`, `10-Q`, `8-K`.

---

## 6. What to store after download

| Artifact | Where (target) | Why |
|---|---|---|
| Raw HTML/XML | Object store (MinIO/S3) | Immutable source of truth |
| Filing metadata | Postgres `filings` | CIK, accession, form, dates, `s3_raw_path`, source URL |
| Parsed sections / chunks | Postgres + vector index | RAG retrieval + citations |
| XBRL facts (optional) | Postgres `financial_facts` | Structured numeric queries |

Always keep **accession number**, **section**, and **source URL** with each chunk so answers remain citable.

---

## 7. How this maps to the Annex / KB platform

| Concern | Location |
|---|---|
| Spec | [SPEC-ingestion.md](../SPEC-ingestion.md) |
| HTTP client | `services/ingestion/.../edgar/http_client.py` |
| Pipeline stages | Fetch → store → parse → chunk → embed (Dagster graph) |
| CIK / accession types | `packages/domain` (`CIK`, `AccessionNumber`) |

`HttpEdgarClient.fetch_latest_filing()` loads submissions, selects the newest matching form, builds the archive URL, and `download_filing_document()` pulls the bytes—with User-Agent and ≤10 req/s limiting.

---

## 8. Common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `403` / empty body | Missing or bad User-Agent | Set company name + email in User-Agent |
| Sudden slowdowns / errors | Exceeded fair-access rate | Cap at 10 req/s; backoff |
| `404` on archive URL | Wrong CIK padding or accession hyphens | Unpad CIK for archive path; strip hyphens from accession |
| Wrong document | Used exhibit instead of primary | Prefer `primaryDocument` from submissions |
| Duplicate work | Re-downloaded same accession | Persist and check ingestion cursor |

---

## 9. Quick checklist

- [ ] Descriptive User-Agent with contact email  
- [ ] Throttle ≤ 10 requests/second  
- [ ] Use 10-digit CIK for `data.sec.gov` paths  
- [ ] Use numeric (unpadded) CIK + hyphen-stripped accession for archive URLs  
- [ ] Store raw bytes immutably + metadata for citations  
- [ ] Prefer incremental pulls for a curated CIK set  

---

## References

- SEC EDGAR & data APIs: [https://www.sec.gov/edgar](https://www.sec.gov/edgar)  
- Data APIs host: [https://data.sec.gov](https://data.sec.gov)  
- Platform architecture §4 (ingestion): [architecture-design.md](architecture-design.md)
