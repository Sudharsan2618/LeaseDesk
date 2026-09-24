"use client";
import { Fragment } from "react";

/** The wizard as a COMPACT HORIZONTAL stepper (spec §3.3-3.6 + decide + review). Each step shows its
 *  chosen value; completed selection steps are clickable to jump back and edit (controlled iteration). */
export type StageKey = "channel" | "partner" | "product" | "asset" | "commercial" | "decide" | "review";

const STAGES: { key: StageKey; label: string }[] = [
  { key: "channel", label: "Channel" },
  { key: "partner", label: "Customer" },
  { key: "product", label: "Product" },
  { key: "asset", label: "Asset" },
  { key: "commercial", label: "Terms" },
  { key: "decide", label: "Pricing" },
  { key: "review", label: "Review" },
];
const GOTO_STEPS = new Set(["channel", "partner", "product", "asset", "commercial"]);

export function WizardRail({ current, done, values, onGoto, busy }: {
  current: StageKey;
  done?: boolean;
  values?: Partial<Record<StageKey, string | null>>;
  onGoto?: (step: StageKey) => void;
  busy?: boolean;
}) {
  const idx = STAGES.findIndex((s) => s.key === current);
  return (
    <div className="panel"><div className="pbody" style={{ padding: "14px 16px" }}>
      <div className="hwiz">
        {STAGES.map((s, i) => {
          const state = done || i < idx ? "done" : i === idx ? "now" : "upcoming";
          const editable = !!onGoto && !busy && state === "done" && GOTO_STEPS.has(s.key);
          const val = values?.[s.key] ?? null;
          const dot =
            state === "done" ? { bg: "var(--accent)", fg: "#fff", ring: "transparent" }
            : state === "now" ? { bg: "var(--accent-soft)", fg: "var(--accent-hover)", ring: "color-mix(in srgb,var(--accent) 32%,transparent)" }
            : { bg: "var(--hair)", fg: "var(--faint)", ring: "transparent" };
          const Cell = editable ? "button" : "div";
          return (
            <Fragment key={s.key}>
              {i > 0 && <span className="hline" style={{ background: i <= idx ? "var(--accent)" : "var(--hair)" }} />}
              <Cell
                onClick={editable ? () => onGoto!(s.key) : undefined}
                title={editable ? "Edit this step" : undefined}
                className={`hstep ${editable ? "hgoto" : ""} ${state === "now" ? "now" : ""}`}>
                <span className="hmark" style={{ background: dot.bg, color: dot.fg, boxShadow: `0 0 0 2px ${dot.ring}` }}>
                  {state === "done" ? "✓" : i + 1}
                </span>
                <span className="hlabel" style={{
                  color: state === "now" ? "var(--ink)" : state === "done" ? "var(--muted)" : "var(--faint)",
                  fontWeight: state === "now" ? 600 : 500,
                }}>{s.label}</span>
                <span className="hval num" title={val ?? undefined}>{val ?? "—"}</span>
                {editable && <span className="hedit">edit</span>}
              </Cell>
            </Fragment>
          );
        })}
      </div>
    </div></div>
  );
}
