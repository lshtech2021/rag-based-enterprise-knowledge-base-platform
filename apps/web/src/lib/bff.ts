export const bffBaseUrl =
  process.env.NEXT_PUBLIC_BFF_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export type SourceCitation = {
  chunk_id: string;
  accession_no: string;
  section: string;
  source_url: string;
};

export type MeResponse = {
  user_id: string;
  roles: string[];
  auth_mode: string;
};

export type ReportResponse = {
  report_id: string;
  template_id: string;
  title: string;
  company: string;
  period: string;
  user_id: string;
  markdown: string;
  citations: Array<SourceCitation & { section_id: string }>;
};

export type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

type SseHandlers = {
  onToken: (token: string) => void;
  onSources: (sources: SourceCitation[]) => void;
  onDone: (answer: string) => void;
};

type StreamQueryOptions = {
  history?: ChatHistoryMessage[];
  signal?: AbortSignal;
};

export async function fetchMe(): Promise<MeResponse> {
  const response = await fetch(`${bffBaseUrl}/v1/me`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load identity (${response.status})`);
  }
  return (await response.json()) as MeResponse;
}

export async function streamQuery(
  question: string,
  handlers: SseHandlers,
  options: StreamQueryOptions = {},
): Promise<void> {
  const response = await fetch(`${bffBaseUrl}/v1/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      question,
      history: options.history ?? [],
    }),
    signal: options.signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Query failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .find((entry) => entry.startsWith("data: "));
      if (!line) continue;
      const payload = JSON.parse(line.slice(6)) as {
        type: string;
        data: unknown;
      };
      if (payload.type === "token") {
        handlers.onToken(String(payload.data));
      } else if (payload.type === "sources") {
        handlers.onSources(payload.data as SourceCitation[]);
      } else if (payload.type === "done") {
        const data = payload.data as { answer: string };
        handlers.onDone(data.answer);
      }
    }
  }
}

export async function createReport(input: {
  company: string;
  period: string;
  template_id?: string;
}): Promise<ReportResponse> {
  const response = await fetch(`${bffBaseUrl}/v1/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      template_id: input.template_id ?? "quarterly_risk_summary",
      company: input.company,
      period: input.period,
    }),
  });
  if (!response.ok) {
    throw new Error(`Report create failed (${response.status})`);
  }
  return (await response.json()) as ReportResponse;
}

export async function getReport(reportId: string): Promise<ReportResponse> {
  const response = await fetch(`${bffBaseUrl}/v1/reports/${reportId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Report fetch failed (${response.status})`);
  }
  return (await response.json()) as ReportResponse;
}

export type IngestResponse = {
  accession_no: string;
  skipped: boolean;
  chunk_count: number;
  s3_raw_path: string | null;
  download_url: string;
};

export async function createIngest(input: {
  cik: string;
  form_types: string[];
  force?: boolean;
}): Promise<IngestResponse> {
  const response = await fetch(`${bffBaseUrl}/v1/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cik: input.cik,
      form_types: input.form_types,
      force: input.force ?? false,
    }),
  });
  if (!response.ok) {
    let detail = `Ingest failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as IngestResponse;
}

export async function downloadFilingRaw(accessionNo: string): Promise<Blob> {
  const response = await fetch(
    `${bffBaseUrl}/v1/filings/${encodeURIComponent(accessionNo)}/raw`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Download failed (${response.status})`);
  }
  return response.blob();
}
