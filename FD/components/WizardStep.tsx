"use client";
import { useEffect, useState } from "react";
import type { Interrupt } from "@/lib/types";
import { eur } from "@/lib/format";

/** One confirm gate in the wizard (spec §3.3-3.6). Renders the picker for the current step, tracks
 *  the salesperson's choice, and confirms — advancing only when the mandatory field is set (the
 *  backend enforces this too). Free-text changes go through the agent chat on the right. */
export function WizardStep({
  interrupt, running, onConfirm,
}: {
  interrupt: Interrupt;
  running: boolean;
  onConfirm: (overrides: Record<string, unknown>) => void;
}) {
  const step = interrupt.step!;
  const p = interrupt.proposed ?? {};
  const str = (v: unknown) => (v === null || v === undefined ? "" : String(v));
  const [pick, setPick] = useState<string | null>(null);
  const [af, setAf] = useState<Record<string, string>>({});   // client-side asset attribute filters
  const [form, setForm] = useState({
    term_months: str(p.term_months), annual_mileage_km: str(p.annual_mileage_km),
    quantity: str(p.quantity ?? 1), special_payment_eur: str(p.special_payment_eur),
    service_maintenance: !!p.service_maintenance, service_tyres: !!p.service_tyres, insurance: !!p.insurance,
  });

  // reset local state whenever the step changes
  useEffect(() => {
    setPick(
      step === "channel" ? (p.channel ?? "internal_sales") :
      step === "partner" ? (p.register_number ?? null) :
      step === "product" ? (p.leasing_product ?? "pkw_km_leasing") :
      step === "asset" ? (p.vehicle_key ?? null) : null,
    );
    setAf({});
    setForm({
      term_months: str(p.term_months), annual_mileage_km: str(p.annual_mileage_km),
      quantity: str(p.quantity ?? 1), special_payment_eur: str(p.special_payment_eur),
      service_maintenance: !!p.service_maintenance, service_tyres: !!p.service_tyres, insurance: !!p.insurance,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, interrupt.reference]);

  function confirm() {
    const ov: Record<string, unknown> =
      step === "channel" ? { channel: pick } :
      step === "partner" ? { register_number: pick } :
      step === "product" ? { leasing_product: pick } :
      step === "asset" ? { vehicle_key: pick } :
      {
        term_months: Number(form.term_months) || null,
        annual_mileage_km: Number(form.annual_mileage_km) || null,
        quantity: Number(form.quantity) || 1,
        special_payment_eur: form.special_payment_eur === "" ? null : Number(form.special_payment_eur),
        service_maintenance: form.service_maintenance, service_tyres: form.service_tyres, insurance: form.insurance,
      };
    onConfirm(ov);
  }

  const blocked =
    (step === "partner" && !pick) || (step === "asset" && !pick) ||
    (step === "commercial" && (!form.term_months || !form.annual_mileage_km));

  return (
    <div className="panel">
      <div className="phead"><h3>{interrupt.title ?? "Confirm"}</h3>
        <span className="chip tag" style={{ marginLeft: "auto" }}>Step</span>
      </div>
      <div className="pbody">
        <p className="mini muted" style={{ marginBottom: 4 }}>{interrupt.prompt}</p>

        {(interrupt.ambiguities?.length ?? 0) > 0 && (
          <div className="banner warn mini" style={{ margin: "8px 0" }}>
            <b>Needs your confirmation:</b>{" "}
            {interrupt.ambiguities!.map((a) => `${a.field} — ${a.reason}`).join(" · ")}
          </div>
        )}

        {step === "channel" && (
          <OptList items={(interrupt.options ?? []).map((o) => ({ id: o.key, label: o.label, sub: o.status }))}
            pick={pick} setPick={setPick} />
        )}
        {step === "partner" && (
          <>
            {interrupt.is_search && (interrupt.candidates?.length ?? 0) > 1 && (
              <div className="banner warn mini" style={{ margin: "8px 0" }}>
                {interrupt.candidates!.length} possible matches — pick the right customer (duplicate check).
              </div>
            )}
            {!interrupt.is_search && (interrupt.candidates?.length ?? 0) > 0 && (
              <p className="mini faint" style={{ margin: "8px 0 0" }}>
                {interrupt.partner_kind === "offer_partner" ? "Offer partners" : "Business partner directory"}
                {" "}· pick one, or type a name to the agent to narrow.
              </p>
            )}
            <OptList
              items={(interrupt.candidates ?? []).map((c) => ({
                id: c.register_number, label: c.legal_name,
                sub: `${c.register_number}${c.legal_form ? " · " + c.legal_form : ""}` }))}
              pick={pick} setPick={setPick}
              empty="No customers found — tell the agent the customer name on the right." />
          </>
        )}
        {step === "product" && (
          <OptList
            items={(interrupt.products ?? []).filter((x) => x.status !== "planned")
              .map((x) => ({ id: x.key, label: x.label, sub: x.asset_category }))}
            pick={pick} setPick={setPick} />
        )}
        {step === "asset" && (() => {
          const cat = interrupt.catalogue ?? [];
          const attrs: { key: keyof typeof cat[number]; label: string }[] = [
            { key: "fuel_type", label: "Fuel" }, { key: "body_type", label: "Body" },
            { key: "transmission", label: "Transmission" }, { key: "seats", label: "Seats" },
          ];
          const rec = (v: typeof cat[number]) => v as unknown as Record<string, unknown>;
          const shown = cat.filter((v) => Object.entries(af).every(
            ([k, val]) => !val || String(rec(v)[k] ?? "") === val));
          const chosen = cat.find((v) => v.key === pick);
          return (
            <>
              <div className="flex flex-wrap gap-x-4 gap-y-2" style={{ margin: "10px 0 4px" }}>
                {attrs.map(({ key, label }) => {
                  const opts = Array.from(new Set(cat.map((v) => rec(v)[key as string])
                    .filter((x) => x !== undefined && x !== null && x !== ""))).map(String);
                  if (opts.length < 2) return null;
                  return (
                    <div key={String(key)} className="flex items-center gap-1.5">
                      <span className="mini faint">{label}</span>
                      {opts.map((o) => (
                        <button key={o} className={`chip ${af[key as string] === o ? "acc" : "tag"}`}
                          onClick={() => setAf({ ...af, [key as string]: af[key as string] === o ? "" : o })}>{o}</button>
                      ))}
                    </div>
                  );
                })}
              </div>
              <OptList
                items={shown.map((v) => ({
                  id: v.key, label: v.label,
                  sub: `${v.fuel_type ?? ""} · ${v.seats ?? "?"} seats · ${eur(v.list_price_net)}` }))}
                pick={pick} setPick={setPick}
                empty="No asset matches these filters — clear a filter or ask the agent." />
              {chosen && (
                <div className="mini" style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--hair)" }}>
                  <div className="font-semibold text-[13px]">{chosen.make} {chosen.commercial_name}</div>
                  <div className="specgrid" style={{ marginTop: 8 }}>
                    <div><div className="k">Fuel</div><div className="v">{chosen.fuel_type ?? "—"}</div></div>
                    <div><div className="k">Transmission</div><div className="v">{chosen.transmission ?? "—"}</div></div>
                    <div><div className="k">Power</div><div className="v">{chosen.engine_power_hp ?? "?"} hp</div></div>
                    <div><div className="k">Body · seats</div><div className="v">{chosen.body_type ?? "—"} · {chosen.seats ?? "?"}</div></div>
                    <div><div className="k">List price</div><div className="v num">{eur(chosen.list_price_net)}</div></div>
                    {chosen.co2_class && <div><div className="k">CO₂</div><div className="v">{chosen.co2_class}</div></div>}
                  </div>
                </div>
              )}
            </>
          );
        })()}
        {step === "commercial" && (
          <div className="stack" style={{ gap: 12, marginTop: 10 }}>
            <div className="grid2" style={{ gap: 12 }}>
              <Field label="Term (months) *"><input className="inp" type="number" value={form.term_months}
                onChange={(e) => setForm({ ...form, term_months: e.target.value })} /></Field>
              <Field label="Annual mileage (km) *"><input className="inp" type="number" value={form.annual_mileage_km}
                onChange={(e) => setForm({ ...form, annual_mileage_km: e.target.value })} /></Field>
              <Field label="Quantity"><input className="inp" type="number" min={1} value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
              <Field label="Special payment (€)"><input className="inp" type="number" value={form.special_payment_eur}
                onChange={(e) => setForm({ ...form, special_payment_eur: e.target.value })} /></Field>
            </div>
            <div className="flex flex-wrap gap-4 mini">
              {(["service_maintenance", "service_tyres", "insurance"] as const).map((k) => (
                <label key={k} className="flex items-center gap-2">
                  <input type="checkbox" checked={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.checked })} />
                  {k === "service_maintenance" ? "Maintenance" : k === "service_tyres" ? "Tyres" : "Insurance"}
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-3" style={{ marginTop: 14 }}>
          <button className="btn primary" onClick={confirm} disabled={running || blocked}>
            {running ? "Working…" : "Confirm & continue"}
          </button>
          {blocked && <span className="mini faint">Pick or fill the required field to continue.</span>}
        </div>
      </div>
    </div>
  );
}

function OptList({ items, pick, setPick, empty }: {
  items: { id: string; label: string; sub?: string | null }[];
  pick: string | null; setPick: (v: string) => void; empty?: string;
}) {
  if (items.length === 0) return <p className="mini faint" style={{ marginTop: 10 }}>{empty ?? "No options."}</p>;
  return (
    <div className="optlist">
      {items.map((it) => (
        <button key={it.id} className={`opt ${pick === it.id ? "on" : ""}`} onClick={() => setPick(it.id)}>
          <span>{it.label}{it.sub ? <span className="mini muted"> · {it.sub}</span> : null}</span>
          {pick === it.id && <span className="ok">✓</span>}
        </button>
      ))}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="fld"><span>{label}</span>{children}</label>;
}
