"use client";
import type { FeedEvent } from "@/lib/types";

export interface FeedLine {
  id: number; label: string; node?: string; band?: FeedEvent["band"]; score?: string;
  detail?: string; await?: boolean; error?: boolean;
}

const BAND_COLOR: Record<string, string> = { GREEN: "var(--green)", YELLOW: "var(--amber)", RED: "var(--rose)" };

export function LiveFeed({ lines, running }: { lines: FeedLine[]; running: boolean }) {
  return (
    <section className="panel">
      <div className="phead">
        <span className={`w-2 h-2 rounded-full ${running ? "pulse" : ""}`} style={{ background: running ? "var(--accent)" : "var(--hair)" }} />
        <h3>Agent activity</h3>
        <span className="mini faint" style={{ marginLeft: "auto" }}>live · from the engine</span>
      </div>
      <div style={{ padding: "8px 12px", maxHeight: 380, overflow: "auto" }}>
        {lines.length === 0 && (
          <div className="mini faint" style={{ textAlign: "center", padding: "22px 8px" }}>
            Nothing running yet. Actions stream their reasoning here.
          </div>
        )}
        {lines.map((l) => (
          <div key={l.id} className="feedline feed-in">
            <span className="d" style={{ background: l.error ? "var(--rose)" : l.await ? "var(--amber)" : "var(--accent)" }} />
            <div style={{ minWidth: 0 }}>
              <div className="text-[13px]">{l.label}</div>
              {(l.detail || l.band) && (
                <div className="mini muted" style={{ display: "flex", gap: 8, marginTop: 2 }}>
                  {l.band && <span style={{ color: BAND_COLOR[l.band] ?? "inherit", fontWeight: 600 }}>{l.band}{l.score ? ` · ${l.score}` : ""}</span>}
                  {l.detail && <span className="num">{l.detail}</span>}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
