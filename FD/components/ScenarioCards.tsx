"use client";
import type { ScenarioRow } from "@/lib/types";
import { eur } from "@/lib/format";
import { BandPill } from "./BandPill";

export function ScenarioCards({
  scenarios, onSelect, selectedLabel, busy,
}: { scenarios: ScenarioRow[]; onSelect?: (l: string) => void; selectedLabel?: string | null; busy?: boolean }) {
  const cheapest = scenarios.reduce<ScenarioRow | null>(
    (m, s) => (!m || Number(s.monthly_gross_eur) < Number(m.monthly_gross_eur) ? s : m), null);
  const fleet = scenarios.some((s) => (s.quantity ?? 1) > 1);
  return (
    <div className="scn">
      {scenarios.map((s) => {
        const sel = selectedLabel === s.scenario;
        return (
          <div key={s.scenario} className={`scard ${sel ? "sel" : ""}`}
            onClick={() => !busy && onSelect?.(s.scenario)} style={{ cursor: onSelect ? "pointer" : "default" }}>
            <div className="font-semibold flex items-center gap-2">
              {s.term_months} mo
              {sel && <span className="mini" style={{ color: "var(--accent-hover)" }}>selected</span>}
              {!sel && cheapest?.scenario === s.scenario && <span className="mini" style={{ color: "var(--green)" }}>lowest</span>}
            </div>
            <div className="big num">{eur(s.monthly_gross_eur)}</div>
            <div className="mini muted">per vehicle · gross</div>
            {fleet && <div className="kv"><span className="k">Fleet ×{s.quantity}</span><span className="num">{eur(s.total_monthly_gross_eur)}</span></div>}
            <div className="kv"><span className="k">Residual</span><span className="num">{s.residual_pct}%</span></div>
            <Bundle s={s} />
            <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <BandPill band={s.band} />
              {s.fits_budget != null && (
                <span className={`chip ${s.fits_budget ? "g" : "r"}`}><span className="dot" />
                  {s.fits_budget ? "within budget" : `over by ${eur(Math.abs(Number(s.budget_headroom_eur ?? 0)))}`}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** The service/insurance bundle a scenario was priced with — so "with insurance / without" is explicit. */
function Bundle({ s }: { s: ScenarioRow }) {
  const items: { k: string; on: boolean }[] = [
    { k: "Maintenance", on: !!s.service_maintenance },
    { k: "Tyres", on: !!s.service_tyres },
    { k: "Insurance", on: !!s.insurance },
  ];
  return (
    <div className="bundle">
      {items.map((it) => (
        <span key={it.k} className={`bpill ${it.on ? "on" : "off"}`}>
          <span className="bmark">{it.on ? "✓" : "—"}</span>{it.k}
        </span>
      ))}
    </div>
  );
}
