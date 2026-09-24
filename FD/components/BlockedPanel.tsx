"use client";
import Link from "next/link";
import type { ExceptionRow } from "@/lib/types";
import { humanizeException, isTerminalBlock } from "@/lib/negative";

/** The actionable blocked state (spec §7.8, §10.2, FR-34/62). Each blocking condition names WHAT
 *  happened → WHY → WHAT is required next. A compliance/terminal block routes to a new variant;
 *  a correctable one points back to the agent. */
export function BlockedPanel({
  exceptions, band, explanation, onAdjust, canAdjust,
}: {
  exceptions: ExceptionRow[];
  band: string | null;
  explanation?: string | null;
  onAdjust?: () => void;
  canAdjust?: boolean;
}) {
  const blocking = exceptions.filter((e) => e.blocking);
  const terminal = blocking.some((e) => isTerminalBlock(e.code));
  const rows = blocking.length ? blocking : exceptions.slice(0, 1);

  return (
    <div className="panel" style={{ borderColor: "color-mix(in srgb,var(--rose) 30%,var(--hair))" }}>
      <div className="phead">
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--rose)" }} />
        <h3 style={{ color: "var(--rose)" }}>Blocked{band ? ` · ${band}` : ""}</h3>
        <span className="mini faint" style={{ marginLeft: "auto" }}>can’t proceed yet</span>
      </div>
      <div className="pbody" style={{ display: "flex", flexDirection: "column" }}>
        {rows.map((e, i) => {
          const m = humanizeException(e);
          return (
            <div key={i} style={{
              padding: i === 0 ? "0 0 12px" : "12px 0",
              borderTop: i === 0 ? "none" : "1px solid var(--hair)",
            }}>
              <div className="text-[13px] font-semibold">{m.what}</div>
              <div className="mini muted" style={{ marginTop: 2 }}>{m.why}</div>
              <div className="mini" style={{ marginTop: 6, color: "var(--accent-hover)" }}>
                <b>Next</b> · {m.next}
              </div>
            </div>
          );
        })}
        {explanation && (
          <p className="mini muted" style={{ marginTop: 12, lineHeight: 1.6, paddingTop: 12, borderTop: "1px solid var(--hair)" }}>
            {explanation}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3" style={{ marginTop: 14 }}>
          {terminal ? (
            <Link href="/offers/new" className="btn primary">Start a new offer</Link>
          ) : canAdjust ? (
            <button className="btn primary" onClick={onAdjust}>Adjust with the agent</button>
          ) : (
            <Link href="/offers/new" className="btn">Start a new offer</Link>
          )}
        </div>
      </div>
    </div>
  );
}
