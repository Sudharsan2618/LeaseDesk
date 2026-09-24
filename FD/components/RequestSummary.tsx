"use client";
import type { Proposed, ProvenanceField } from "@/lib/types";
import { eur } from "@/lib/format";

/** The four info states shown on every field (spec §7.6, FR-14). */
type State = "established" | "confirmed" | "requires_confirmation" | "needs_action";
const LABELS: Record<State, string> = {
  established: "set", confirmed: "confirmed", requires_confirmation: "to confirm", needs_action: "needed",
};

export function InfoChip({ state }: { state: State }) {
  return <span className={`istate ${state}`}><span className="d" />{LABELS[state]}</span>;
}

interface Row { label: string; value: string | null; state: State; }

function rowsFromProvenance(p: Record<string, ProvenanceField | null>): Row[] {
  const pick = (k: string, label: string, fmt?: (v: string | number) => string): Row => {
    const f = p[k];
    const has = f && f.value !== null && f.value !== undefined && f.value !== "";
    return {
      label,
      value: has ? (fmt ? fmt(f!.value as string) : String(f!.value)) : null,
      state: (f?.info_state as State) ?? "needs_action",
    };
  };
  return [
    pick("customer_name", "Customer"),
    pick("vehicle_make", "Vehicle make"),
    pick("vehicle_model", "Model"),
    pick("list_price_net", "List price", (v) => eur(v)),
    pick("quantity", "Quantity"),
    pick("term_months", "Term (months)"),
    pick("annual_mileage_km", "Mileage/yr", (v) => `${Number(v).toLocaleString()} km`),
    pick("special_payment_eur", "Special payment", (v) => eur(v)),
  ];
}

function rowsFromProposed(p: Proposed): Row[] {
  const has = (v: unknown) => v !== null && v !== undefined && v !== "";
  const mk = (label: string, v: unknown, fmt?: (x: unknown) => string): Row => ({
    label, value: has(v) ? (fmt ? fmt(v) : String(v)) : null,
    state: has(v) ? "requires_confirmation" : "needs_action",
  });
  const services = [p.service_maintenance && "maintenance", p.service_tyres && "tyres", p.insurance && "insurance"]
    .filter(Boolean).join(" + ");
  const budget = (p.constraints ?? []).find((c) => c.kind === "budget" || c.kind === "monthly_cap");
  return [
    mk("Customer", p.register_number ?? p.company_hint),
    mk("Vehicle", p.vehicle_key ? `${p.make ?? ""} ${p.model ?? ""}`.trim() || p.vehicle_key : (p.make || p.model)),
    mk("Quantity", p.quantity),
    mk("Term (months)", p.term_months),
    mk("Mileage/yr", p.annual_mileage_km, (v) => `${Number(v).toLocaleString()} km`),
    mk("Services", services || null),
    ...(budget ? [{ label: "Budget", value: `${budget.currency ?? ""}${Number(budget.value).toLocaleString()} · ${budget.basis ?? "?"}`, state: "requires_confirmation" as State }] : []),
  ];
}

export function RequestSummary({
  proposed, provenance, title = "Request so far",
}: {
  proposed?: Proposed | null;
  provenance?: Record<string, ProvenanceField | null>;
  title?: string;
}) {
  const rows = provenance ? rowsFromProvenance(provenance) : proposed ? rowsFromProposed(proposed) : [];
  if (rows.length === 0) return null;
  return (
    <div className="panel">
      <div className="phead"><h3>{title}</h3>
        <span className="mini faint" style={{ marginLeft: "auto" }}>✓ set · ◐ to confirm · ⚠ needed</span>
      </div>
      <div className="pbody" style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {rows.map((r) => (
          <div key={r.label} className="prov">
            <span className="muted mini">{r.label}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {r.value && <span className="num mini">{r.value}</span>}
              <InfoChip state={r.state} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
