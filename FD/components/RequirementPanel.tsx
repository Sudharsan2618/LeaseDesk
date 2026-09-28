"use client";
import { useEffect, useState } from "react";
import type { CatalogueVehicle, FieldRow, ReferenceData } from "@/lib/types";
import { getReference, getVehicles } from "@/lib/api";

/** State-driven intake (docs/16): the live field-state view. Each field shows its status; pending
 *  fields can be confirmed or edited inline; anything can also be changed by talking to the agent on
 *  the right. "Confirm all & price" accepts the remaining proposals and moves to pricing. */
const OVERRIDE_KEY: Record<string, string> = {
  channel: "channel", product: "leasing_product", term: "term_months",
  mileage: "annual_mileage_km", quantity: "quantity", special_payment: "special_payment_eur",
  maintenance: "service_maintenance", tyres: "service_tyres", insurance: "insurance",
};
const NUMERIC = new Set(["term", "mileage", "quantity", "special_payment"]);
const TOGGLE = new Set(["maintenance", "tyres", "insurance"]);
const CHAT_ONLY = new Set(["customer"]);

const STATUS: Record<string, { cls: string; label: string }> = {
  confirmed: { cls: "g", label: "confirmed" },
  proposed: { cls: "y", label: "to confirm" },
  stale: { cls: "r", label: "re-confirm" },
  unset: { cls: "r", label: "needs input" },
};

export function RequirementPanel({
  fields, busy, onConfirmField, onProceed, onEdit,
}: {
  fields: FieldRow[];
  busy: boolean;
  onConfirmField: (field: string) => void;
  onProceed: () => void;
  onEdit: (overrides: Record<string, unknown>) => void;
}) {
  const [ref, setRef] = useState<ReferenceData | null>(null);
  const [vehicles, setVehicles] = useState<CatalogueVehicle[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<string>("");
  useEffect(() => {
    getReference().then(setRef).catch(() => {});
    getVehicles().then(setVehicles).catch(() => {});
  }, []);

  const required = fields.filter((f) => f.required);
  const done = required.filter((f) => f.status === "confirmed").length;
  const allConfirmed = done === required.length;

  function startEdit(f: FieldRow) {
    setEditing(f.field);
    setDraft(f.value == null ? "" : String(f.value));
  }
  function commit(f: FieldRow, value: unknown) {
    setEditing(null);
    onEdit({ [OVERRIDE_KEY[f.field]]: value });
  }

  return (
    <div className="panel">
      <div className="phead"><h3>Requirement</h3>
        <span className="mini muted" style={{ marginLeft: "auto" }}>{done}/{required.length} confirmed</span>
      </div>
      <div className="pbody stack" style={{ gap: 4 }}>
        <p className="mini muted" style={{ marginBottom: 4 }}>
          Confirm or edit each field here, or just tell the agent on the right (e.g. “48 months”,
          “change the customer to …”, “confirm all”).
        </p>
        {fields.map((f) => {
          const st = STATUS[f.status] ?? STATUS.unset;
          const pending = f.status !== "confirmed";
          const isEditing = editing === f.field;
          return (
            <div key={f.field} className="freq">
              <span className={`chip ${st.cls}`} style={{ minWidth: 92, justifyContent: "center" }}>
                <span className="dot" />{st.label}</span>
              <span className="freq-lbl">{f.label}</span>
              {!isEditing && (
                <span className="freq-val num" title={String(f.value ?? "")}>
                  {f.value == null || f.value === "" ? <span className="faint">—</span>
                    : TOGGLE.has(f.field) ? (f.value ? "yes" : "no") : String(f.value)}
                </span>
              )}
              {f.field === "asset" && (
                <select className="inp freq-inp" value={f.option_key ?? ""} disabled={busy || vehicles.length === 0}
                  aria-label="Choose vehicle" onChange={(e) => {
                    const selected = vehicles.find((v) => v.key === e.target.value);
                    if (selected) onEdit({ vehicle_key: selected.key, make: selected.make, model: selected.commercial_name });
                  }}>
                  <option value="">Choose a vehicle…</option>
                  {vehicles.map((v) => <option key={v.key} value={v.key}>
                    {v.label} · €{Number(v.list_price_net).toLocaleString()} net
                  </option>)}
                </select>
              )}
              {isEditing && NUMERIC.has(f.field) && (
                <input autoFocus className="inp freq-inp num" type="number" value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") commit(f, Number(draft)); if (e.key === "Escape") setEditing(null); }} />
              )}
              {isEditing && (f.field === "channel" || f.field === "product") && (
                <select autoFocus className="inp freq-inp" value={draft}
                  onChange={(e) => { setDraft(e.target.value); commit(f, e.target.value); }}>
                  {(f.field === "channel" ? ref?.channels : ref?.leasing_products)?.map((o) => (
                    <option key={o.key} value={o.key}>{o.label}</option>
                  ))}
                </select>
              )}
              <span className="freq-actions">
                {TOGGLE.has(f.field) ? (
                  <button className="btn" style={{ padding: "3px 9px", fontSize: 12 }} disabled={busy}
                    onClick={() => onEdit({ [OVERRIDE_KEY[f.field]]: !f.value })}>
                    {f.value ? "Remove" : "Add"}</button>
                ) : CHAT_ONLY.has(f.field) ? (
                  <span className="mini faint">edit in chat</span>
                ) : f.field === "asset" ? null : !isEditing ? (
                  <button className="freq-edit" disabled={busy} onClick={() => startEdit(f)}>edit</button>
                ) : null}
                {pending && !TOGGLE.has(f.field) && (
                  <button className="btn go" style={{ padding: "3px 10px", fontSize: 12 }} disabled={busy}
                    onClick={() => onConfirmField(f.field)}>Confirm</button>
                )}
              </span>
            </div>
          );
        })}
        <div className="flex flex-wrap items-center gap-3" style={{ marginTop: 10 }}>
          <button className="btn go" onClick={onProceed} disabled={busy}>
            {allConfirmed ? "Price it" : "Confirm all & price"}</button>
        </div>
      </div>
    </div>
  );
}
