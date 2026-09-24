import { WORKFLOW_STEPS, stepIndex } from "@/lib/format";

/** Numbered lifecycle stepper (matches the redesign mockup). */
export function StatusSpine({ status }: { status: string }) {
  const active = stepIndex(status);
  return (
    <div className="stepper">
      {WORKFLOW_STEPS.map((s, i) => {
        const done = i < active, now = i === active;
        return (
          <span key={s.key} className="flex items-center">
            <span className={`st ${done ? "done" : now ? "now" : ""}`}>
              <span className="n">{done ? "✓" : i + 1}</span>
              {now ? <b>{s.label}</b> : <span>{s.label}</span>}
            </span>
            {i < WORKFLOW_STEPS.length - 1 && <span className={`bar ${i < active ? "on" : ""}`} />}
          </span>
        );
      })}
    </div>
  );
}
