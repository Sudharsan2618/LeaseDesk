import type { ProvenanceField } from "@/lib/types";

const TONE: Record<string, string> = {
  CONFIRMED: "var(--green)", ESTABLISHED: "var(--green)",
  INFERRED: "var(--amber)", REQUIRES_CONFIRMATION: "var(--amber)",
  MISSING: "var(--faint)", INVALID: "var(--rose)", INCONSISTENT: "var(--rose)", SEED: "var(--faint)",
};

/** A value with its origin — value · status · source (docs/01). */
export function ProvChip({ label, field }: { label: string; field?: ProvenanceField | null }) {
  const status = field?.status ?? "MISSING";
  const color = TONE[status] ?? "var(--muted)";
  return (
    <div className="prov">
      <span className="muted">{label}</span>
      <span style={{ textAlign: "right" }}>
        <span className="num" style={{ color: "var(--ink)" }}>{field?.value ?? "—"}</span>
        <span className="st" style={{ marginLeft: 8, color }}>
          {status.toLowerCase().replace(/_/g, " ")}{field?.source ? ` · ${field.source}` : ""}
        </span>
      </span>
    </div>
  );
}
