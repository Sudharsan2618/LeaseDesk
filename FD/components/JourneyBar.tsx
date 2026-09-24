"use client";
import { WORKFLOW_STEPS, stepIndex, humanStatus } from "@/lib/format";

/** A compact status spine per offer row (DESIGN.md: status as a spine of steps, not scattered pills).
 *  Shows the humanized stage label + a segmented bar filled to the offer's position in the journey. */
export function JourneyBar({ status, blocked }: { status: string; blocked?: boolean }) {
  const idx = stepIndex(status);
  return (
    <div>
      <div className="text-[13px]" style={{ color: blocked ? "var(--rose)" : "var(--ink)" }}>
        {humanStatus(status)}
      </div>
      <div className="jbar" aria-hidden>
        {WORKFLOW_STEPS.map((_, i) => (
          <span key={i} className={`jseg ${blocked && i <= idx ? "blocked" : i < idx ? "on" : i === idx ? "now" : ""}`} />
        ))}
      </div>
    </div>
  );
}
