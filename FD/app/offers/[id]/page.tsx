"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { getOffer } from "@/lib/api";
import { useOfferStream } from "@/lib/useStream";
import type { Snapshot } from "@/lib/types";
import { eur, humanStatus } from "@/lib/format";
import { humanizeException } from "@/lib/negative";
import { BandPill, OutcomePill } from "@/components/BandPill";
import { AgentChat } from "@/components/AgentChat";
import { WizardRail, type StageKey } from "@/components/WizardRail";
import { RequirementPanel } from "@/components/RequirementPanel";
import { RequestSummary } from "@/components/RequestSummary";
import { BudgetFitPanel } from "@/components/BudgetFit";
import { ScenarioCards } from "@/components/ScenarioCards";
import { BlockedPanel } from "@/components/BlockedPanel";
import { InfoTip } from "@/components/InfoTip";
import { CalcBreakdownPanel } from "@/components/DataPanels";

export default function Workspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pendingMsg, setPendingMsg] = useState<string | null>(null);
  const { lines, running, run } = useOfferStream();

  useEffect(() => { getOffer(id).then(setSnap).catch((e) => setErr(String(e))); }, [id]);

  const offer = snap?.offer;
  const intakeInt = snap?.interrupts.find((i) => i.type === "agent_turn");
  const gate = snap?.interrupts.find((i) => i.type === "workspace_gate");
  const review = snap?.interrupts.find((i) => i.type === "human_review");
  const generated = offer?.workflow_status === "OFFER_GENERATED";
  const priced = !!offer?.calc;
  const hasBudget = !!(offer?.proposed?.constraints ?? []).find(
    (c) => c.kind === "budget" || c.kind === "monthly_cap");

  const fields = intakeInt?.field_state ?? snap?.field_state ?? [];
  const pendingFields = intakeInt?.pending ?? [];
  const FIELD_STAGE: Record<string, StageKey> = {
    channel: "channel", customer: "partner", product: "product", asset: "asset",
    term: "commercial", mileage: "commercial", quantity: "commercial",
    special_payment: "commercial", maintenance: "commercial", tyres: "commercial", insurance: "commercial",
  };
  const blocked = !intakeInt && !gate && !review && offer?.final_outcome === "BLOCKED";
  const stage: StageKey =
    intakeInt ? (FIELD_STAGE[pendingFields[0]] ?? "channel")
    : review || generated ? "review"
    : gate || priced ? "decide"
    : blocked ? "asset"
    : "partner";

  async function intakeTurn(body: Record<string, unknown>) {
    const s = await run(`/offers/${id}/intake/stream`, body);
    if (s) setSnap(s);
  }
  async function sendChat(m: string) {
    setPendingMsg(m);
    try { await intakeTurn({ message: m }); } finally { setPendingMsg(null); }
  }
  async function selectScenario(label: string) {
    const s = await run(`/offers/${id}/select/stream`, { scenario_label: label });
    if (s) setSnap(s);
  }
  async function generate() { const s = await run(`/offers/${id}/generate/stream`, {}); if (s) setSnap(s); }
  async function adjust() { const s = await run(`/offers/${id}/adjust/stream`, {}); if (s) setSnap(s); }
  async function reviewDecide(decision: "confirm" | "return") {
    const s = await run(`/offers/${id}/review/stream`, { decision }); if (s) setSnap(s);
  }
  async function gotoStep(step: string) {
    const s = await run(`/offers/${id}/goto/stream`, { step }); if (s) setSnap(s);
  }

  if (err) return <Shell><div className="banner bad mini">{err}</div></Shell>;
  if (!offer) return <Shell><div className="mini faint">Loading…</div></Shell>;

  // per-step chosen values for the horizontal wizard
  const p = offer.proposed ?? {};
  const pvv = (k: string) => (offer.provenance?.[k]?.value ?? null) as string | number | null;
  const humanize = (s?: string | null) => (s ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : null);
  const make = (pvv("vehicle_make") as string) ?? p.make ?? null;
  const model = (pvv("vehicle_model") as string) ?? p.model ?? null;
  const stepValues: Partial<Record<StageKey, string | null>> = {
    channel: humanize(p.channel),
    partner: (pvv("customer_name") as string) ?? p.register_number ?? p.company_hint ?? null,
    product: humanize(p.leasing_product),
    asset: make ? `${make}${model ? " " + model : ""}` : null,
    commercial: p.term_months ? `${p.term_months}mo · ${p.quantity ?? 1}×` : null,
    decide: offer.calc ? `${eur(offer.calc.monthly_gross_eur)}/mo` : null,
    review: generated ? "Generated" : null,
  };

  return (
    <div className="obench">
      {/* LEFT — the wizard, scrolls on its own under the fixed header */}
      <div className="obench-main">
      <div className="flex items-center gap-3 mb-1 mini faint">
        <Link href="/" className="hover:text-ink">Dashboard</Link><span>/</span>
        <span className="num muted">{offer.reference}</span>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4">
        <h1 className="num text-[20px] font-semibold tracking-tight">{offer.reference}</h1>
        {priced && <BandPill band={offer.band} />}
        {(priced || stage === "review") && <OutcomePill outcome={offer.final_outcome} />}
        {priced && offer.calc && (
          <span className="num text-[15px]"><b>{eur(offer.calc.total_monthly_gross_eur)}</b>
            <span className="muted mini">/mo fleet · {eur(offer.calc.monthly_gross_eur)}/veh</span></span>
        )}
        <span className="ml-auto mini muted">
          {intakeInt ? "Building the request" : humanStatus(offer.workflow_status)}</span>
      </div>

        <div className="wbmain">
          <WizardRail current={stage} done={generated} busy={running} values={stepValues}
            onGoto={(intakeInt || gate) ? (s) => gotoStep(s) : undefined} />

          {!intakeInt && offer.provenance && (
            <RequestSummary provenance={offer.provenance} title="Requirement Summary" />
          )}

          {intakeInt && (
            <RequirementPanel fields={fields} busy={running}
              onConfirmField={(f) => intakeTurn({ confirm_field: f })}
              onProceed={() => intakeTurn({ proceed: true })}
              onEdit={(ov) => intakeTurn({ overrides: ov })} />
          )}

          {!intakeInt && review && (
            <div className="panel"><div className="phead"><h3>Review &amp; generate</h3>
              <span className="chip acc" style={{ marginLeft: "auto" }}>human decision</span></div>
              <div className="pbody stack">
                <p className="mini muted">{review.prompt}</p>
                <div className="mini">Outcome: <b>{review.outcome}</b>
                  {review.selected_scenario_label ? ` · scenario ${review.selected_scenario_label}` : ""}</div>
                {(review.exceptions?.length ?? 0) > 0 && (
                  <div className="stack" style={{ gap: 8 }}>
                    {review.exceptions!.map((e, i) => {
                      const m = humanizeException(e);
                      return (
                        <div key={i} className="mini">
                          <span style={{ color: e.blocking ? "var(--rose)" : "var(--amber)", fontWeight: 600 }}>{m.what}</span>
                          <span className="muted"> {m.why}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
                <div className="flex flex-wrap gap-3">
                  <button className="btn go" onClick={() => reviewDecide("confirm")}
                    disabled={running || review.can_generate === false}>Confirm &amp; generate</button>
                  <button className="btn" onClick={() => reviewDecide("return")} disabled={running}>Return for correction</button>
                </div>
              </div></div>
          )}

          {blocked && (
            <BlockedPanel exceptions={offer.exceptions} band={offer.band}
              explanation={offer.explanation_pricing} onAdjust={adjust} canAdjust={false} />
          )}

          {/* GENERATED — terminal state: show the finished offer, not the scenario picker */}
          {!intakeInt && !review && !blocked && generated && (
            <>
              <div className="panel"><div className="phead"><h3>Offer generated</h3>
                <span className="chip g" style={{ marginLeft: "auto" }}><span className="dot" />Done</span></div>
                <div className="pbody stack">
                  <p className="mini muted">The offer is finalised from the selected scenario. Start a new
                    offer for another request.</p>
                  <div className="kv"><span className="k">Scenario</span><b>{offer.selected_scenario_label}</b></div>
                  <div className="kv"><span className="k">Monthly · per vehicle</span>
                    <span className="num">{eur(offer.calc?.monthly_gross_eur)}</span></div>
                  <div className="kv"><span className="k">Monthly · fleet</span>
                    <span className="num">{eur(offer.calc?.total_monthly_gross_eur)}</span></div>
                  <div className="flex flex-wrap items-center gap-3" style={{ marginTop: 4 }}>
                    <Link href="/offers/new" className="btn primary">New offer</Link>
                    <Link href="/" className="btn">Back to dashboard</Link>
                  </div>
                </div></div>
              {offer.calc && <CalcBreakdownPanel calc={offer.calc} />}
            </>
          )}

          {/* PRICED, not yet generated — the scenario picker */}
          {!intakeInt && !review && !blocked && !generated && (gate || priced) && (
            <>
              <div className="panel"><div className="phead"><h3>Pricing &amp; scenarios</h3>
                {(offer.explanation_pricing || offer.explanation_scenarios) && (
                  <InfoTip title="Why these scenarios">
                    {offer.explanation_pricing && <p>{offer.explanation_pricing}</p>}
                    {offer.explanation_scenarios && <p className="muted" style={{ marginTop: 6 }}>{offer.explanation_scenarios}</p>}
                  </InfoTip>
                )}
              </div>
                <div className="pbody stack">
                  <p className="mini muted">Scenarios are built around your requested term, honouring your
                    choices. Pick one, adjust with the agent, or generate. Nothing is locked.</p>
                  <ScenarioCards scenarios={offer.scenarios} onSelect={selectScenario}
                    selectedLabel={offer.selected_scenario_label} busy={running} />
                  <div className="flex flex-wrap items-center gap-3">
                    <button className="btn go" onClick={generate} disabled={running || !offer.selected_scenario_id}>
                      Generate offer</button>
                    <button className="btn" onClick={adjust} disabled={running}>Adjust with agent</button>
                  </div>
                </div></div>
              <BudgetFitPanel offerId={id} hasBudget={hasBudget} />
              {offer.calc && <CalcBreakdownPanel calc={offer.calc} />}
            </>
          )}
        </div>
      </div>

      {/* RIGHT — the agent, a fixed full-height rail; only its message log scrolls */}
      <aside className="obench-side">
        <AgentChat transcript={offer.transcript ?? []} lines={lines} running={running}
          canSend={!!intakeInt} onSend={sendChat} pendingMessage={pendingMsg} />
      </aside>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="wrap">{children}</div>;
}
