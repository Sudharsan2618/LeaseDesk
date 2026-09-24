"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getAuditAll } from "@/lib/api";
import type { AuditAllRow } from "@/lib/types";
import { humanStatus } from "@/lib/format";

/** Global, cross-offer audit trail — the governance record ("Humans govern"), pulled out of the
 *  workbench into its own destination. Newest first, filterable by actor. */
export default function AuditPage() {
  const [rows, setRows] = useState<AuditAllRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [actor, setActor] = useState<"ALL" | "USER" | "SYSTEM">("ALL");

  useEffect(() => { getAuditAll().then(setRows).catch((e) => setErr(String(e))); }, []);

  const filtered = useMemo(
    () => (rows ?? []).filter((r) => actor === "ALL" || r.actor_kind === actor),
    [rows, actor]);

  return (
    <div className="wrap">
      <div className="flex items-end justify-between mb-5 gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[22px] font-semibold tracking-tight">Audit trail</h1>
            {rows && <span className="chip tag num">{filtered.length}</span>}
          </div>
          <p className="mini muted mt-1">Every governed action across all offers — who did what, and why.</p>
        </div>
        <div className="flex items-center gap-1.5">
          {(["ALL", "USER", "SYSTEM"] as const).map((a) => (
            <button key={a} onClick={() => setActor(a)}
              className={`btn ${actor === a ? "primary" : ""}`} style={{ padding: "6px 12px", fontSize: 12 }}>
              {a === "ALL" ? "All" : humanStatus(a)}
            </button>
          ))}
        </div>
      </div>

      {err && <div className="banner bad mini">Couldn’t reach the backend on :8100. <span className="num">{err}</span></div>}

      {rows && filtered.length === 0 && !err && (
        <div className="panel"><div className="pbody" style={{ textAlign: "center", padding: "48px 16px" }}>
          <p className="text-[15px] font-medium">No audit events{actor !== "ALL" ? ` from ${humanStatus(actor)}` : " yet"}</p>
          <p className="mini muted mt-1">Actions are recorded here as offers move through the flow.</p>
        </div></div>
      )}

      {filtered.length > 0 && (
        <div className="panel" style={{ overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="ledger">
              <thead><tr>
                <th>When</th><th>Offer</th><th>Customer</th>
                <th>Event</th><th>Actor</th><th>Reason</th><th aria-label="open" />
              </tr></thead>
              <tbody>
                {filtered.map((r, i) => (
                  <tr key={i} onClick={() => (location.href = `/offers/${r.offer_id}`)}>
                    <td className="num muted mini" style={{ whiteSpace: "nowrap" }}>
                      {new Date(r.at).toLocaleString()}
                    </td>
                    <td><Link href={`/offers/${r.offer_id}`} className="ref" onClick={(e) => e.stopPropagation()}>{r.reference}</Link></td>
                    <td className="muted">{r.customer ?? <span className="faint">—</span>}</td>
                    <td>{humanStatus(r.event)}</td>
                    <td><span className={`chip ${r.actor_kind === "USER" ? "acc" : "tag"}`}>{humanStatus(r.actor_kind)}</span></td>
                    <td className="muted mini">{r.reason ?? <span className="faint">—</span>}</td>
                    <td className="r" style={{ width: 28 }}><span className="chev">→</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!rows && !err && (
        <div className="panel"><div className="pbody mini faint" style={{ padding: "40px 16px", textAlign: "center" }}>Loading audit trail…</div></div>
      )}
    </div>
  );
}
