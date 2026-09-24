import type { Band, Outcome } from "./types";

export function eur(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "string" ? Number(v) : v;
  if (Number.isNaN(n)) return String(v);
  return "€" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export const bandTone: Record<Band, { dot: string; text: string; soft: string; label: string }> = {
  GREEN: { dot: "bg-green", text: "text-green", soft: "bg-green-soft", label: "Green" },
  YELLOW: { dot: "bg-amber", text: "text-amber", soft: "bg-amber-soft", label: "Yellow" },
  RED: { dot: "bg-rose", text: "text-rose", soft: "bg-rose-soft", label: "Red" },
};

export const outcomeTone: Record<Outcome, { text: string; soft: string; label: string }> = {
  READY: { text: "text-green", soft: "bg-green-soft", label: "Ready" },
  REQUIRES_ACTION: { text: "text-amber", soft: "bg-amber-soft", label: "Requires action" },
  BLOCKED: { text: "text-rose", soft: "bg-rose-soft", label: "Blocked" },
};

export function humanStatus(s: string): string {
  return s
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// canonical workflow order for the status spine
export const WORKFLOW_STEPS = [
  { key: "intake", label: "Intake", statuses: ["DRAFT", "UNDERSTANDING", "CONTEXT_REQUIRED"] },
  { key: "price", label: "Price & score", statuses: ["CONTEXT_COMPLETE", "VALIDATION_REQUIRED", "READY_FOR_CALCULATION", "CALCULATED"] },
  { key: "scenarios", label: "Scenarios", statuses: ["SCENARIOS_AVAILABLE", "SCENARIO_SELECTED"] },
  { key: "review", label: "Review", statuses: ["PENDING_HUMAN_REVIEW", "APPROVED", "RETURNED"] },
  { key: "final", label: "Final", statuses: ["FINAL_VALIDATION"] },
  { key: "offer", label: "Offer", statuses: ["OFFER_GENERATED"] },
] as const;

export function stepIndex(status: string): number {
  const i = WORKFLOW_STEPS.findIndex((s) => (s.statuses as readonly string[]).includes(status));
  return i === -1 ? 0 : i;
}
