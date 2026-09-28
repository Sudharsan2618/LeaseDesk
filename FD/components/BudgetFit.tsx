"use client";
import { useEffect, useState } from "react";
import { getBudgetFit, getVehicles } from "@/lib/api";
import type { BudgetFit } from "@/lib/types";
import { eur } from "@/lib/format";
import { BandDot } from "./BandPill";

/** "Which asset fits the budget?" (Phase 6 / doc 13 §3.2). The agent enumerates the filtered
 *  catalogue, the deterministic ENGINE prices each candidate, and this ranks them by fit. */
export function BudgetFitPanel({ offerId, hasBudget, onChoose }: {
  offerId: string; hasBudget: boolean; onChoose?: (vehicleKey: string) => void;
}) {
  const [data, setData] = useState<BudgetFit | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!hasBudget) return;
    setLoading(true);
    Promise.all([getBudgetFit(offerId), getVehicles()])
      .then(([bf, vs]) => { setData(bf); setLabels(Object.fromEntries(vs.map((v) => [v.key, v.label]))); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [offerId, hasBudget]);

  if (!hasBudget) return null;
  if (loading && !data) return (
    <div className="panel"><div className="pbody mini faint">Pricing each option against your budget…</div></div>
  );
  if (!data || !data.budget) return null;

  const b = data.budget;
  const basisLabel = b.basis === "annual" ? "per year (fleet)" : b.basis === "monthly"
    ? "per month (fleet)" : b.basis === "per_vehicle" ? "per vehicle / month"
    : b.basis === "acquisition" ? "acquisition" : "whole contract";

  return (
    <div className="panel">
      <div className="phead"><h3>Fit to your budget</h3>
        <span className="chip acc" style={{ marginLeft: "auto" }}>engine-priced</span></div>
      <div className="pbody" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <p className="mini muted">
          Budget <b className="num">{b.currency ?? ""}{Number(b.value).toLocaleString()}</b> · {basisLabel}.
          The engine prices each candidate; ranked by fit.
        </p>
        {data.candidates.map((c) => {
          const over = c.fits_budget === false;
          const headroom = c.budget_headroom_eur != null ? Number(c.budget_headroom_eur) : null;
          return (
            <div key={c.vehicle_key} style={{
              display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 9,
              border: "1px solid var(--hair)",
              background: over ? "color-mix(in srgb,var(--rose-soft) 40%,transparent)"
                : c.fits_budget ? "color-mix(in srgb,var(--green-soft) 40%,transparent)" : "var(--surface)",
            }}>
              <BandDot band={c.band ?? null} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="text-[13px] font-medium">{labels[c.vehicle_key] ?? c.vehicle_key}</div>
                {c.priced ? (
                  <div className="mini muted num">
                    {eur(c.total_monthly_gross_eur)}/mo fleet · {eur(c.contract_total_eur)} contract
                    {c.budget_metric_eur != null && ` · ${eur(c.budget_metric_eur)} ${b.basis}`}
                  </div>
                ) : <div className="mini faint">not priceable ({c.band ?? "—"})</div>}
              </div>
              {c.fits_budget != null && (
                <span className={`chip ${c.fits_budget ? "g" : "r"}`}><span className="dot" />
                  {c.fits_budget
                    ? (headroom != null ? `${eur(headroom)} under` : "fits")
                    : (headroom != null ? `${eur(Math.abs(headroom))} over` : "over")}</span>
              )}
              {onChoose && c.priced && c.fits_budget !== false && (
                <button className="btn" style={{ padding: "4px 9px", fontSize: 11 }}
                  onClick={() => onChoose(c.vehicle_key)}>Use vehicle</button>
              )}
            </div>
          );
        })}
        {data.candidates.length === 0 && <p className="mini faint">No candidates to compare — set an asset filter or category.</p>}
      </div>
    </div>
  );
}
