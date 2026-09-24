"use client";
import type { ScenarioRow } from "@/lib/types";
import { eur } from "@/lib/format";
import { BandPill } from "./BandPill";

export function ScenarioTable({
  scenarios,
  onSelect,
  selectedLabel,
  busy,
}: {
  scenarios: ScenarioRow[];
  onSelect?: (label: string) => void;
  selectedLabel?: string | null;
  busy?: boolean;
}) {
  const cheapest = scenarios.reduce<ScenarioRow | null>(
    (m, s) => (!m || Number(s.monthly_gross_eur) < Number(m.monthly_gross_eur) ? s : m),
    null,
  );
  const fleet = scenarios.some((s) => (s.quantity ?? 1) > 1);
  return (
    <div className="rounded-[10px] border bg-surface overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[12px] text-faint border-b">
            <th className="font-medium px-4 py-2.5">Term</th>
            <th className="font-medium px-4 py-2.5 text-right">Per vehicle gross</th>
            {fleet && <th className="font-medium px-4 py-2.5 text-right">Fleet total gross</th>}
            <th className="font-medium px-4 py-2.5 text-right">Residual</th>
            <th className="font-medium px-4 py-2.5">Risk</th>
            {onSelect && <th className="px-4 py-2.5" />}
          </tr>
        </thead>
        <tbody>
          {scenarios.map((s) => {
            const selected = selectedLabel === s.scenario;
            return (
              <tr key={s.scenario} className={`border-b last:border-0 ${selected ? "bg-accent-soft/50" : "hover:bg-ground/60"} transition-colors`}>
                <td className="px-4 py-3 font-medium">
                  {s.term_months} mo
                  {cheapest?.scenario === s.scenario && (
                    <span className="ml-2 text-[10px] text-green font-medium">lowest / mo</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right num font-medium">{eur(s.monthly_gross_eur)}</td>
                {fleet && <td className="px-4 py-3 text-right num font-medium">{eur(s.total_monthly_gross_eur)}</td>}
                <td className="px-4 py-3 text-right num text-muted">{s.residual_pct}%</td>
                <td className="px-4 py-3"><BandPill band={s.band} /></td>
                {onSelect && (
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onSelect(s.scenario)}
                      disabled={busy}
                      className={`text-[13px] font-medium px-3 py-1.5 rounded-[6px] transition-colors ${
                        selected ? "bg-accent text-white" : "border hover:bg-ground"
                      } disabled:opacity-40`}
                    >
                      {selected ? "Selected" : "Select"}
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
