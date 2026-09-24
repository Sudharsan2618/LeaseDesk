import type {
  AuditAllRow,
  BudgetFit,
  CatalogueCustomer,
  CatalogueVehicle,
  FeedEvent,
  OfferListRow,
  PartnerCandidate,
  ReferenceData,
  Snapshot,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8100";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const listOffers = () => getJSON<OfferListRow[]>("/offers");
export const getOffer = (id: string) => getJSON<Snapshot>(`/offers/${id}`);
export const getVehicles = () => getJSON<CatalogueVehicle[]>("/catalogue/vehicles");
export const getCustomers = () => getJSON<CatalogueCustomer[]>("/catalogue/customers");
export const getReference = () => getJSON<ReferenceData>("/catalogue/reference");
export const getPartners = (q: string) =>
  getJSON<PartnerCandidate[]>(`/catalogue/partners?q=${encodeURIComponent(q)}`);
export const getBudgetFit = (id: string) => getJSON<BudgetFit>(`/offers/${id}/budget-fit`);
export const getAudit = (id: string) =>
  getJSON<{ event: string; actor_kind: string; reason: string | null; at: string }[]>(
    `/offers/${id}/audit`,
  );
export const getAuditAll = () => getJSON<AuditAllRow[]>("/audit");

/**
 * POST a body and consume the Server-Sent-Events stream from the backend.
 * Native EventSource is GET-only, so we read the fetch body stream ourselves.
 * onEvent fires per parsed SSE event; resolves when the stream ends.
 */
export async function streamPost(
  path: string,
  body: unknown,
  onEvent: (e: FeedEvent) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    const txt = await res.text().catch(() => "");
    throw new Error(`${res.status} ${txt}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const blocks = buf.split("\n\n");
    buf = blocks.pop() ?? "";
    for (const block of blocks) emit(block, onEvent);
  }
  if (buf.trim()) emit(buf, onEvent);
}

function emit(block: string, onEvent: (e: FeedEvent) => void) {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data && event === "message") return;
  let parsed: Record<string, unknown> = {};
  try {
    parsed = data ? JSON.parse(data) : {};
  } catch {
    parsed = {};
  }
  if (event === "node")
    onEvent({ kind: "node", node: parsed.node as string, label: parsed.label as string,
      band: parsed.band as FeedEvent["band"], score: parsed.score as string,
      detail: parsed.detail as string });
  else if (event === "await") onEvent({ kind: "await", label: parsed.label as string });
  else if (event === "snapshot") onEvent({ kind: "snapshot", snapshot: parsed as unknown as Snapshot });
  else if (event === "done") onEvent({ kind: "done" });
  else if (event === "error") onEvent({ kind: "error", detailText: parsed.detail as string });
}
