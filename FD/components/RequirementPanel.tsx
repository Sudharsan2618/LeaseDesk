"use client";
import { useEffect, useMemo, useState } from "react";
import type { CatalogueCustomer, CatalogueVehicle, FieldRow, Proposed, ReferenceData, RefOption } from "@/lib/types";
import { getCustomers, getReference, getSettings, getVehicles, type EditableSetting } from "@/lib/api";

const REQUIRED = ["channel", "customer", "product", "asset", "term", "mileage"];
const LABELS: Record<string, string> = {
  channel: "Sales channel", customer: "Customer", product: "Leasing product",
  asset: "Vehicle", term: "Lease term", mileage: "Annual mileage",
};
const OVERRIDE_KEY: Record<string, string> = {
  channel: "channel", customer: "register_number", product: "leasing_product",
  term: "term_months", mileage: "annual_mileage_km", quantity: "quantity",
  special_payment: "special_payment_eur", maintenance: "service_maintenance",
  tyres: "service_tyres", insurance: "insurance",
};
const TOGGLE = new Set(["maintenance", "tyres", "insurance"]);
const STATUS: Record<string, { cls: string; label: string }> = {
  confirmed: { cls: "g", label: "confirmed" },
  proposed: { cls: "y", label: "to confirm" },
  stale: { cls: "r", label: "re-confirm" },
  unset: { cls: "r", label: "needs input" },
};

type Choice = { key: string; label: string; detail?: string; status?: string; overrides: Record<string, unknown> };
type Policy = {
  term?: { preferred?: number[] };
  mileage?: { min_annual_km?: number; max_annual_km?: number; baseline_annual_km?: number; step_km?: number };
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}
function textKey(value: unknown) { return String(value ?? "").toLowerCase().replace(/[\s_-]/g, ""); }
function toggleOn(value: unknown) { return value === true || String(value).toLowerCase() === "yes"; }

export function RequirementPanel({
  fields, pending = [], proposed = {}, busy, onConfirmField, onProceed, onEdit, onChoose,
}: {
  fields: FieldRow[];
  pending?: string[];
  proposed?: Proposed;
  busy: boolean;
  onConfirmField: (field: string) => void;
  onProceed: () => void;
  onEdit: (overrides: Record<string, unknown>) => void;
  onChoose: (field: string, overrides: Record<string, unknown>) => void;
}) {
  const [ref, setRef] = useState<ReferenceData | null>(null);
  const [vehicles, setVehicles] = useState<CatalogueVehicle[]>([]);
  const [customers, setCustomers] = useState<CatalogueCustomer[]>([]);
  const [settings, setSettings] = useState<EditableSetting[]>([]);
  const [dataError, setDataError] = useState<string | null>(null);
  const [loadingChoices, setLoadingChoices] = useState(true);
  const [query, setQuery] = useState("");
  const [customValue, setCustomValue] = useState("");
  const [viewField, setViewField] = useState<string | null>(null);
  const [editingDetail, setEditingDetail] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    Promise.allSettled([getReference(), getVehicles(), getCustomers(), getSettings()])
      .then(([reference, assetRows, customerRows, config]) => {
        if (!live) return;
        const failures: string[] = [];
        if (reference.status === "fulfilled") setRef(reference.value); else failures.push("products/channels");
        if (assetRows.status === "fulfilled") setVehicles(assetRows.value); else failures.push("vehicles");
        if (customerRows.status === "fulfilled") setCustomers(customerRows.value); else failures.push("customers");
        if (config.status === "fulfilled") setSettings(config.value);
        if (failures.length) setDataError(`Couldn’t load ${failures.join(", ")}. You can still use the choices that loaded.`);
      })
      .catch((error) => { if (live) setDataError(String(error)); })
      .finally(() => { if (live) setLoadingChoices(false); });
    return () => { live = false; };
  }, []);

  const byField = useMemo(() => new Map(fields.map((field) => [field.field, field])), [fields]);
  const required = REQUIRED.map((name) => byField.get(name)).filter((field): field is FieldRow => !!field);
  const done = required.filter((field) => field.status === "confirmed").length;
  const nextPending = pending.find((field) => REQUIRED.includes(field))
    ?? required.find((field) => field.status !== "confirmed")?.field;
  const nextPendingIndex = nextPending ? REQUIRED.indexOf(nextPending) : required.length;
  const activeFieldName = viewField ?? nextPending;
  const active = activeFieldName ? byField.get(activeFieldName) : undefined;
  const activeIndex = Math.max(0, REQUIRED.indexOf(activeFieldName ?? REQUIRED[0]));
  const selectedValue = active?.field === "channel" ? proposed.channel
    : active?.field === "customer" ? proposed.register_number
    : active?.field === "product" ? proposed.leasing_product
    : active?.field === "asset" ? proposed.vehicle_key
    : active?.field === "term" ? proposed.term_months
    : active?.field === "mileage" ? proposed.annual_mileage_km : undefined;
  const policy = useMemo(
    () => record(settings.find((item) => item.kind === "policy")?.data) as unknown as Policy,
    [settings],
  );
  const termOptions = policy.term?.preferred?.length ? policy.term.preferred : [24, 36, 48, 60];
  const mileageOptions = useMemo(() => {
    const mileage = policy.mileage;
    if (!mileage) return [10000, 15000, 20000, 25000, 30000, 40000];
    const min = Number(mileage.min_annual_km ?? 5000);
    const max = Number(mileage.max_annual_km ?? 40000);
    const step = Math.max(1, Number(mileage.step_km ?? 5000));
    const values: number[] = [];
    for (let value = min; value <= max && values.length < 40; value += step) values.push(value);
    return values.length ? values : [Number(mileage.baseline_annual_km ?? 15000)];
  }, [policy]);

  const channelChoices: Choice[] = (ref?.channels ?? []).map((option: RefOption) => ({
    key: option.key, label: option.name_en ?? option.label ?? option.key,
    detail: option.status === "active" ? "Available channel" : "Inactive channel",
    status: option.status,
    overrides: { channel: option.key },
  }));
  const productChoices: Choice[] = (ref?.leasing_products ?? []).map((option) => ({
    key: option.key, label: option.name_en ?? option.label ?? option.key,
    detail: option.description_en || (option.status === "active" ? "Available product" : "Not yet active"),
    status: option.status,
    overrides: { leasing_product: option.key },
  }));
  const customerChoices: Choice[] = customers.map((customer) => ({
    key: customer.register_number, label: customer.legal_name,
    detail: customer.legal_form ?? "Company",
    overrides: { register_number: customer.register_number },
  }));
  const vehicleChoices: Choice[] = vehicles.map((vehicle) => ({
    key: vehicle.key, label: vehicle.label,
    detail: `${vehicle.fuel_type ?? "Vehicle"} · €${Number(vehicle.list_price_net).toLocaleString()} net`,
    overrides: { vehicle_key: vehicle.key, make: vehicle.make, model: vehicle.commercial_name },
  }));
  const choices: Choice[] = active?.field === "channel" ? channelChoices
    : active?.field === "customer" ? customerChoices
    : active?.field === "product" ? productChoices
    : active?.field === "asset" ? vehicleChoices
    : active?.field === "term" ? termOptions.map((months) => ({
      key: String(months), label: `${months} months`, detail: `${months / 12} ${months === 12 ? "year" : "years"}`,
      overrides: { term_months: months },
    }))
    : active?.field === "mileage" ? mileageOptions.map((km) => ({
      key: String(km), label: `${km.toLocaleString()} km / year`, detail: km === Number(policy.mileage?.baseline_annual_km) ? "Standard annual mileage" : undefined,
      overrides: { annual_mileage_km: km },
    })) : [];
  const visibleChoices = choices.filter((choice) =>
    !query || `${choice.label} ${choice.detail ?? ""}`.toLowerCase().includes(query.toLowerCase()));

  function isCurrent(choice: Choice) {
    if (!active) return false;
    const configuredKey = active.option_key ?? selectedValue;
    if (configuredKey != null) return String(configuredKey) === choice.key;
    if (active.field === "term" || active.field === "mileage") return String(active.value) === choice.key;
    return textKey(active.value) === textKey(choice.label);
  }
  function choose(choice: Choice) {
    if (!active) return;
    setQuery(""); setCustomValue(""); setViewField(null);
    onChoose(active.field, choice.overrides);
  }
  function commitCustom() {
    if (!active || !customValue.trim()) return;
    const number = Number(customValue);
    if ((active.field === "term" || active.field === "mileage") && (!Number.isFinite(number) || number <= 0)) return;
    const fieldOverride = active.field === "mileage" ? { annual_mileage_km: number }
      : active.field === "term" ? { term_months: number }
      : { [OVERRIDE_KEY[active.field]]: number };
    onChoose(active.field, fieldOverride);
    setCustomValue(""); setViewField(null);
  }

  const filteredChoices = active?.field === "customer" || active?.field === "asset";
  const missingChoices = !loadingChoices && !dataError && choices.length === 0;
  const isRequiredComplete = done === required.length && required.length > 0;

  return (
    <div className="panel req-panel">
      <div className="phead">
        <h3>Requirement</h3>
        <span className="mini muted" style={{ marginLeft: "auto" }}>{done}/{required.length} required confirmed</span>
      </div>
      <div className="pbody req-body">
        {active ? (
          <section className="req-question" aria-labelledby="req-question-title">
            <div className="req-question-head">
              <div>
                <h4 id="req-question-title">{active.status === "confirmed" ? `Review ${LABELS[active.field]}` : `Choose ${LABELS[active.field]?.toLowerCase()}`}</h4>
                <p className="mini muted">
                  {active.status === "proposed" || active.status === "stale"
                    ? `The request currently suggests ${String(active.value ?? "a value")}. Select it to confirm, or choose another option.`
                    : "Choose an option from the current catalogue. Selecting one confirms it and moves to the next required question."}
                </p>
              </div>
              <span className="req-count">{activeIndex + 1} of {required.length}</span>
            </div>

            <div className="req-progress" aria-label={`${done} of ${required.length} required fields confirmed`}>
              {required.map((field, index) => <button key={field.field} type="button"
                className={`req-progress-step ${field.status === "confirmed" ? "is-done" : ""} ${field.field === active.field ? "is-current" : ""}`}
                disabled={busy || (index > nextPendingIndex && field.status !== "confirmed")}
                aria-label={`${index + 1}: ${LABELS[field.field]}, ${field.status}`}
                aria-current={field.field === active.field ? "step" : undefined}
                onClick={() => { setViewField(field.field); setQuery(""); }}>
                <span className="req-progress-mark">{field.status === "confirmed" ? "✓" : index + 1}</span>
                <span>{LABELS[field.field]}</span>
              </button>)}
            </div>

            {(filteredChoices || choices.length > 7) && (
              <input className="inp req-search" type="search"
                aria-label={`Search ${LABELS[active.field]?.toLowerCase()} options`}
                placeholder={`Search ${LABELS[active.field]?.toLowerCase()} options…`}
                value={query} onChange={(event) => setQuery(event.target.value)} disabled={busy} />
            )}

            {loadingChoices && <p className="mini muted req-empty">Loading available options…</p>}
            {dataError && <div className="banner bad mini req-empty">
              Couldn’t load the available choices. Refresh this offer to try again. <span className="num">{dataError}</span>
            </div>}
            {missingChoices && <p className="mini muted req-empty">There are no configured options for this field yet. Add them in Settings or describe what you need in the agent chat.</p>}
            {!loadingChoices && !dataError && choices.length > 0 && visibleChoices.length === 0 && (
              <p className="mini muted req-empty">No matches. Try a shorter search, or describe a different value in the agent chat.</p>
            )}

            <div className="req-choices" role="list" aria-label={`${LABELS[active.field]} choices`}>
              {visibleChoices.map((choice, index) => {
                const selected = isCurrent(choice);
                const unavailable = ["planned", "inactive"].includes((choice.status ?? "").toLowerCase());
                return <button key={choice.key} type="button" role="listitem"
                  className={`req-choice ${selected ? "is-selected" : ""}`}
                  disabled={busy || unavailable} onClick={() => choose(choice)}>
                  <span className="req-choice-key">{index + 1}</span>
                  <span className="req-choice-copy">
                    <span className="req-choice-title">{choice.label}</span>
                    {choice.detail && <span className="req-choice-detail">{choice.detail}</span>}
                  </span>
                  <span className="req-choice-meta">
                    {selected && <span className="req-current">Current</span>}
                    {unavailable && <span className="mini muted">Not active</span>}
                    {!unavailable && <span aria-hidden="true">↵</span>}
                  </span>
                </button>;
              })}
            </div>

            {(active.field === "term" || active.field === "mileage") && (
              <form className="req-custom" onSubmit={(event) => { event.preventDefault(); commitCustom(); }}>
                <label htmlFor="req-custom-value">Something else</label>
                <div className="req-custom-control">
                  <input id="req-custom-value" className="inp num" type="number" min="1" step="1"
                    placeholder={active.field === "term" ? "Enter months" : "Enter km per year"}
                    value={customValue} onChange={(event) => setCustomValue(event.target.value)} disabled={busy} />
                  <button className="btn" type="submit" disabled={busy || !customValue.trim()}>Use value</button>
                </div>
              </form>
            )}

            <div className="req-question-foot">
              <button className="req-back" type="button" disabled={busy || activeIndex === 0}
                onClick={() => { setViewField(REQUIRED[activeIndex - 1]); setQuery(""); }}>
                ← Previous question
              </button>
              <span className="mini muted">You can also describe a different choice in the agent chat.</span>
            </div>
          </section>
        ) : isRequiredComplete ? (
          <section className="req-complete">
            <span className="req-complete-mark" aria-hidden="true">✓</span>
            <div><h4>Required details confirmed</h4>
              <p className="mini muted">Your required details are confirmed. Start the pricing calculation to build the offer scenarios.</p></div>
            <button className="btn go" onClick={onProceed} disabled={busy}>Start pricing calculation</button>
          </section>
        ) : <p className="mini muted">No required fields are available for this request.</p>}

        <details className="req-details">
          <summary>Other request details <span className="mini muted">{fields.filter((field) => !REQUIRED.includes(field.field)).length} fields</span></summary>
          <div className="req-details-list">
            {fields.filter((field) => !REQUIRED.includes(field.field)).map((field) => {
              const status = STATUS[field.status] ?? STATUS.unset;
              const editing = editingDetail === field.field;
              const confirmable = TOGGLE.has(field.field) || (field.value != null && field.value !== "");
              return <div className="req-detail-row" key={field.field}>
                <span className={`chip ${status.cls}`}><span className="dot" />{status.label}</span>
                <span className="freq-lbl">{field.label}</span>
                <span className="req-detail-value num">{field.value == null || field.value === "" ? "—"
                  : TOGGLE.has(field.field) ? (toggleOn(field.value) ? "yes" : "no") : String(field.value)}</span>
                {TOGGLE.has(field.field) ? <div className="req-detail-actions">
                  <button className="btn" disabled={busy}
                    onClick={() => onEdit({ [OVERRIDE_KEY[field.field]]: !toggleOn(field.value) })}>{toggleOn(field.value) ? "Remove" : "Add"}</button>
                  {field.status !== "confirmed" && confirmable && <button className="btn go req-confirm-small" disabled={busy}
                    onClick={() => onConfirmField(field.field)}>Confirm</button>}
                </div> : editing ? <CustomDetailEdit field={field} busy={busy} onCancel={() => setEditingDetail(null)}
                  onSave={(value) => { setEditingDetail(null); onEdit({ [OVERRIDE_KEY[field.field]]: value }); }} />
                  : <div className="req-detail-actions">
                    <button className="freq-edit" disabled={busy} onClick={() => setEditingDetail(field.field)}>edit</button>
                    {field.status !== "confirmed" && confirmable && <button className="btn go req-confirm-small" disabled={busy}
                      onClick={() => onConfirmField(field.field)}>Confirm</button>}
                  </div>}
              </div>;
            })}
          </div>
        </details>

      </div>
    </div>
  );
}

function CustomDetailEdit({ field, busy, onCancel, onSave }: {
  field: FieldRow; busy: boolean; onCancel: () => void; onSave: (value: number) => void;
}) {
  const [value, setValue] = useState(field.value == null ? "" : String(field.value));
  return <form className="req-detail-edit" onSubmit={(event) => { event.preventDefault(); if (value) onSave(Number(value)); }}>
    <input className="inp num" type="number" min="0" value={value} disabled={busy}
      aria-label={`Edit ${field.label}`} onChange={(event) => setValue(event.target.value)} />
    <button className="freq-edit" type="submit" disabled={busy || !value}>save</button>
    <button className="freq-edit" type="button" disabled={busy} onClick={onCancel}>cancel</button>
  </form>;
}
