import type { Band, Outcome } from "@/lib/types";

const BAND: Record<Band, { cls: string; label: string }> = {
  GREEN: { cls: "g", label: "Green" },
  YELLOW: { cls: "y", label: "Yellow" },
  RED: { cls: "r", label: "Red" },
};
const OUT: Record<Outcome, { cls: string; label: string }> = {
  READY: { cls: "g", label: "Ready" },
  REQUIRES_ACTION: { cls: "y", label: "Requires action" },
  BLOCKED: { cls: "r", label: "Blocked" },
};

export function BandDot({ band }: { band: Band | null }) {
  if (!band) return <span className="inline-block w-2 h-2 rounded-full" style={{ background: "var(--hair)" }} />;
  return <span className={`chip ${BAND[band].cls}`}><span className="dot" /></span>;
}

export function BandPill({ band }: { band: Band | null }) {
  if (!band) return <span className="faint mini">—</span>;
  const t = BAND[band];
  return <span className={`chip ${t.cls}`}><span className="dot" />{t.label}</span>;
}

export function OutcomePill({ outcome }: { outcome: Outcome }) {
  const t = OUT[outcome];
  return <span className={`chip ${t.cls}`}>{t.label}</span>;
}
