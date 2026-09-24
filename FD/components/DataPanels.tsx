"use client";
import { useEffect, useState } from "react";
import type { CalcBreakdown, ScoringDetail } from "@/lib/types";
import { getAudit } from "@/lib/api";
import { eur, humanStatus } from "@/lib/format";

function KV({ k, v, hint, strong }: { k: string; v: string; hint?: string; strong?: boolean }) {
  return (
    <div className="kv">
      <span className="k">{k}{hint && <span className="faint"> · {hint}</span>}</span>
      <span className={`num ${strong ? "font-semibold" : ""}`} style={{ color: "var(--ink)" }}>{v}</span>
    </div>
  );
}
const Eyebrow = ({ t }: { t: string }) => (
  <div className="mini faint" style={{ textTransform: "uppercase", letterSpacing: ".04em", margin: "10px 0 4px" }}>{t}</div>
);

export function CalcBreakdownPanel({ calc }: { calc: CalcBreakdown }) {
  const q = calc.quantity ?? 1;
  const has = (v?: string) => Number(v ?? 0) > 0;
  return (
    <section className="panel">
      <div className="phead"><h3>How this was computed</h3><span className="mini faint" style={{ marginLeft: "auto" }}>deterministic engine</span></div>
      <div className="pbody">
        <Eyebrow t="Rate build-up" />
        <KV k="Reference rate" hint="Bundesbank" v={`${calc.reference_rate_pct}%`} />
        <KV k="+ Funding spread" hint="term + asset" v={`${calc.funding_rate_pct}%`} />
        <KV k="+ Commercial margin" hint="base + risk + deal" v={`${calc.commercial_margin_pct}%`} />
        <div style={{ borderTop: "1px solid var(--hair)", margin: "4px 0", paddingTop: 2 }} />
        <KV k="Customer finance rate" v={`${calc.customer_finance_rate_pct}%`} strong />

        <Eyebrow t="Amortisation → residual (per vehicle)" />
        <KV k="Net capital cost" v={eur(calc.netcap_eur)} />
        <KV k="Residual · PV" v={`${eur(calc.residual_value_amount_eur)} · ${eur(calc.pv_residual_eur)}`} />
        <KV k="Base lease · monthly net" v={eur(calc.base_lease_eur)} />
        {has(calc.service_maintenance_eur) && <KV k="+ Maintenance" v={eur(calc.service_maintenance_eur)} />}
        {has(calc.service_tyres_eur) && <KV k="+ Tyres" v={eur(calc.service_tyres_eur)} />}
        {has(calc.insurance_eur) && <KV k="+ Insurance" v={eur(calc.insurance_eur)} />}
        <div style={{ borderTop: "1px solid var(--hair)", margin: "4px 0" }} />
        <KV k="Monthly net" v={eur(calc.monthly_net_eur)} />
        <KV k={`+ VAT ${calc.vat_pct}%`} v={`→ ${eur(calc.monthly_gross_eur)}`} />
        <KV k="Monthly gross (per vehicle)" v={eur(calc.monthly_gross_eur)} strong />
        {q > 1 && (<><div style={{ borderTop: "1px solid var(--hair)", margin: "4px 0" }} />
          <KV k={`Fleet total gross (× ${q})`} v={eur(calc.total_monthly_gross_eur)} strong /></>)}

        <Eyebrow t="Contract" />
        <KV k="Total mileage" v={`${calc.contract_mileage_km.toLocaleString()} km`} />
        <KV k="Excess/km" v={eur(calc.mileage_settlement_per_km_eur)} />

        <div className="flex flex-wrap gap-1.5" style={{ marginTop: 10, paddingTop: 8, borderTop: "1px solid var(--hair)" }}>
          {Object.values(calc.policies).map((v, i) => v ? <span key={i} className="chip tag num">{v}</span> : null)}
        </div>
      </div>
    </section>
  );
}

export function RiskFactorsPanel({ scoring }: { scoring: ScoringDetail }) {
  const color = scoring.band === "GREEN" ? "var(--green)" : scoring.band === "YELLOW" ? "var(--amber)" : "var(--rose)";
  return (
    <section className="panel">
      <div className="phead"><h3>Risk factors</h3>
        <span className="mini font-semibold" style={{ marginLeft: "auto", color }}>{scoring.band} · <span className="num">{scoring.score}</span></span>
      </div>
      <div className="pbody">
        {scoring.hard_blocks.length > 0 && (
          <div className="banner bad mini" style={{ marginBottom: 10 }}>Hard blocks: {scoring.hard_blocks.join(", ")}</div>
        )}
        {scoring.factors.map((f) => {
          const pct = Math.max(0, Math.min(100, Number(f.score)));
          return (
            <div key={f.name} style={{ padding: "6px 0" }}>
              <div className="flex justify-between mini"><span>{humanStatus(f.name)}</span>
                <span className="num muted">w {(Number(f.weight) * 100).toFixed(0)}% · {f.score} → <b style={{ color: "var(--ink)" }}>{f.contribution}</b></span></div>
              <div className="bar2"><i style={{ width: `${pct}%`, background: color }} /></div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function AuditTimeline({ id }: { id: string }) {
  const [rows, setRows] = useState<{ event: string; actor_kind: string; reason: string | null; at: string }[]>([]);
  useEffect(() => { getAudit(id).then(setRows).catch(() => setRows([])); }, [id]);
  if (rows.length === 0) return null;
  return (
    <section className="panel">
      <div className="phead"><h3>Audit trail</h3></div>
      <div style={{ padding: "8px 12px", maxHeight: 260, overflow: "auto" }}>
        {rows.map((r, i) => (
          <div key={i} className="feedline">
            <span className="d" style={{ background: "color-mix(in srgb,var(--accent) 50%,transparent)" }} />
            <div style={{ minWidth: 0 }}>
              <div className="mini">{humanStatus(r.event)}</div>
              <div className="mini faint num">{new Date(r.at).toLocaleTimeString()} · {r.actor_kind}{r.reason ? ` · ${r.reason}` : ""}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
