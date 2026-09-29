"use client";

import { useEffect, useMemo, useState } from "react";
import { getSettings, putSetting, type EditableSetting } from "@/lib/api";

const SECTIONS = [
  { kind: "policy", title: "Calculation policy", detail: "Terms, mileage, residual values, funding spreads, margins, limits, risk weights and eligibility." },
  { kind: "reference_data", title: "Products & channels", detail: "Business lines, leasing products, asset categories, channels and their workflow rules." },
  { kind: "vehicles", title: "Vehicle catalogue", detail: "Vehicle identities, specifications, categories, prices and selectable attributes." },
  { kind: "companies", title: "Customers & risk profiles", detail: "Customer directory, recommendation defaults, credit limits, KYC and sanctions mock data." },
  { kind: "engine_inputs", title: "Calculation inputs", detail: "Reference rate, VAT, their displayed sources and mock asset-assessment result." },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<EditableSetting[]>([]);
  const [selected, setSelected] = useState(SECTIONS[0].kind);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const current = settings.find((item) => item.kind === selected);
  const section = useMemo(() => SECTIONS.find((item) => item.kind === selected)!, [selected]);
  const dirty = !!current && draft !== JSON.stringify(current.data, null, 2);

  useEffect(() => {
    let active = true;
    getSettings().then((rows) => {
      if (!active) return;
      setSettings(rows);
      setDraft(JSON.stringify(rows.find((item) => item.kind === selected)?.data ?? {}, null, 2));
    }).catch((e) => { if (active) setError(String(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selected]);

  const save = async () => {
    if (!current) return;
    let parsed: Record<string, unknown>;
    try {
      const value: unknown = JSON.parse(draft);
      if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("The document must be a JSON object.");
      parsed = value as Record<string, unknown>;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid JSON");
      return;
    }
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await putSetting(selected, current.revision, parsed);
      setSettings((rows) => rows.map((row) => row.kind === selected ? updated : row));
      setDraft(JSON.stringify(updated.data, null, 2));
      setSaved(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="wrap">
      <div className="mb-5">
        <h1 className="text-[22px] font-semibold tracking-tight">Settings</h1>
        <p className="mini muted mt-1">Edit the live offer catalogue and calculation configuration.</p>
      </div>

      <div className="panel" style={{ overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 290px) minmax(0, 1fr)", minHeight: 600 }}>
          <nav aria-label="Settings categories" style={{ borderRight: "1px solid var(--hair)", padding: 10 }}>
            {SECTIONS.map((item) => {
              const active = item.kind === selected;
              return <button key={item.kind} onClick={() => {
                if (dirty && !window.confirm("Discard your unsaved settings changes?")) return;
                setSelected(item.kind);
                setDraft(JSON.stringify(settings.find((row) => row.kind === item.kind)?.data ?? {}, null, 2));
                setSaved(false); setError(null); setLoading(false);
              }}
                style={{ width: "100%", display: "block", textAlign: "left", cursor: "pointer", border: 0,
                  borderRadius: 7, padding: "11px 12px", marginBottom: 3,
                  color: active ? "var(--accent)" : "var(--ink)",
                  background: active ? "var(--accent-tint)" : "transparent" }}>
                <span style={{ display: "block", fontSize: 13, fontWeight: 600 }}>{item.title}</span>
                <span className="mini muted" style={{ display: "block", marginTop: 3, lineHeight: 1.45 }}>{item.detail}</span>
              </button>;
            })}
          </nav>

          <section style={{ minWidth: 0, padding: "20px 22px" }}>
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <h2 style={{ fontSize: 17, fontWeight: 650 }}>{section.title}</h2>
                <p className="mini muted mt-1">Changes take effect for new pricing and catalogue reads as soon as they are saved.</p>
              </div>
              {current && <span className="mini muted">Revision {current.revision}{current.updated_at ? ` · saved ${new Date(current.updated_at).toLocaleString()}` : ""}</span>}
            </div>

            <div style={{ marginTop: 18 }}>
              <label htmlFor="settings-json" className="mini muted" style={{ display: "block", marginBottom: 7 }}>
                Complete settings document · JSON
              </label>
              <textarea id="settings-json" value={draft} onChange={(event) => { setDraft(event.target.value); setSaved(false); }}
                spellCheck={false} disabled={loading || !current}
                style={{ display: "block", width: "100%", minHeight: 430, resize: "vertical", boxSizing: "border-box",
                  padding: 14, border: "1px solid var(--hair)", borderRadius: 8, background: "var(--surface-2)",
                  color: "var(--ink)", fontFamily: "var(--mono)", fontSize: 12.5, lineHeight: 1.55 }} />
            </div>

            {error && <div className="banner bad mini" style={{ marginTop: 12, whiteSpace: "pre-wrap" }}>{error}</div>}
            {saved && <div className="banner mini" style={{ marginTop: 12 }}>Saved. New requests will use revision {current?.revision}.</div>}
            {loading && <p className="mini muted mt-3">Loading settings…</p>}

            <div className="flex items-center justify-between gap-3 mt-4">
              <p className="mini muted">Saves create a revision and keep the prior value in change history.</p>
              <div className="flex gap-2">
                <button className="btn" disabled={!dirty || saving} onClick={() => current && setDraft(JSON.stringify(current.data, null, 2))}>Discard</button>
                <button className="btn primary" disabled={!dirty || saving || loading} onClick={() => void save()}>
                  {saving ? "Saving…" : "Save changes"}
                </button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
