"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { listOffers } from "@/lib/api";
import type { OfferListRow } from "@/lib/types";
import { BandPill } from "@/components/BandPill";
import { JourneyBar } from "@/components/JourneyBar";
import { eur } from "@/lib/format";

export default function Inbox() {
  const [rows, setRows] = useState<OfferListRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { listOffers().then(setRows).catch((e) => setErr(String(e))); }, []);

  const count = rows?.length ?? 0;

  return (
    <div className="wrap">
      <div className="flex items-end justify-between mb-5 gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[22px] font-semibold tracking-tight">Dashboard</h1>
            {rows && <span className="chip tag num">{count}</span>}
          </div>
          <p className="mini muted mt-1">Every offer, its risk band, and where it is in the journey.</p>
        </div>
        <Link href="/offers/new" className="btn primary">New offer</Link>
      </div>

      {err && (
        <div className="banner bad mini">Couldn’t reach the backend on :8100. <span className="num">{err}</span></div>
      )}

      {rows && rows.length === 0 && (
        <div className="panel"><div className="pbody" style={{ textAlign: "center", padding: "56px 16px" }}>
          <p className="text-[15px] font-medium">No offers yet</p>
          <p className="mini muted mt-1 mb-4">Describe a leasing request in plain language to begin.</p>
          <Link href="/offers/new" className="btn primary">Create your first offer</Link>
        </div></div>
      )}

      {rows && rows.length > 0 && (
        <div className="panel" style={{ overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="ledger">
              <thead><tr>
                <th>Reference</th><th>Customer</th><th>Vehicle</th>
                <th>Journey</th><th>Risk</th>
                <th className="r">Monthly · fleet</th><th aria-label="open" />
              </tr></thead>
              <tbody>
                {rows.map((r) => {
                  const blocked = r.readiness === "BLOCKED" || r.workflow_status === "BLOCKED";
                  return (
                    <tr key={r.id} onClick={() => (location.href = `/offers/${r.id}`)}>
                      <td><Link href={`/offers/${r.id}`} className="ref" onClick={(e) => e.stopPropagation()}>{r.reference}</Link></td>
                      <td>{r.customer ?? <span className="faint">—</span>}</td>
                      <td className="muted">{r.vehicle ?? <span className="faint">—</span>}</td>
                      <td style={{ minWidth: 150 }}><JourneyBar status={r.workflow_status} blocked={blocked} /></td>
                      <td><BandPill band={r.band} /></td>
                      <td className="r num">{r.fleet_monthly_eur
                        ? <b>{eur(r.fleet_monthly_eur)}</b>
                        : <span className="faint">—</span>}</td>
                      <td className="r" style={{ width: 28 }}><span className="chev">→</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {!rows && !err && (
        <div className="panel"><div className="pbody mini faint" style={{ padding: "40px 16px", textAlign: "center" }}>Loading offers…</div></div>
      )}
    </div>
  );
}
