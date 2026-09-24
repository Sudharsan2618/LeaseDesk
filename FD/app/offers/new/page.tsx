"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { useOfferStream } from "@/lib/useStream";
import { AgentChat } from "@/components/AgentChat";
import { WizardRail } from "@/components/WizardRail";
import { ACTOR_EMAIL } from "@/lib/role";
import type { ChatMessage } from "@/lib/types";

const EXAMPLES = [
  "Lease 3 BMW X1 for Musterlogistik, 36 months, 20,000 km/yr, with maintenance and insurance.",
  "I need 4-seater electric cars, 30 of them insured — budget €300k a month.",
];

/** New offer = the same 60/40 workbench in COMPOSE mode. The agent chat on the right IS the intake;
 *  the first message creates the offer and continues on its own page. No separate NL-box screen. */
export default function NewOffer() {
  const router = useRouter();
  const { lines, running, run } = useOfferStream();
  const [sent, setSent] = useState<ChatMessage[]>([]);

  async function create(message: string) {
    setSent([{ role: "user", content: message }]);
    const s = await run("/offers/nl/stream", { nl_request: message, created_by_email: ACTOR_EMAIL.SALES });
    if (s?.thread_id) router.push(`/offers/${s.thread_id}`);
    else setSent([]);   // stream failed — let them retry
  }

  return (
    <div className="obench">
      {/* LEFT — the journey ahead */}
      <div className="obench-main">
      <div className="flex items-center gap-3 mb-1 mini faint">
        <Link href="/" className="hover:text-ink">Dashboard</Link><span>/</span><span className="muted">New offer</span>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4">
        <h1 className="text-[20px] font-semibold tracking-tight">New offer</h1>
        <span className="ml-auto mini muted">Describe the request — the agent builds it</span>
      </div>

        <div className="wbmain">
          <WizardRail current="channel" />
          <div className="panel"><div className="pbody stack">
            <div>
              <h3 className="h2">Start with a sentence</h3>
              <p className="mini muted" style={{ marginTop: 4 }}>
                Include what you know — vehicle, customer, term, quantity, budget. The agent extracts the
                rest and asks only for what’s missing. You confirm each step.
              </p>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <span className="mini faint">Try one:</span>
              {EXAMPLES.map((ex) => (
                <button key={ex} className="opt" onClick={() => !running && create(ex)} disabled={running}>
                  <span className="mini">{ex}</span>
                </button>
              ))}
            </div>
          </div></div>
        </div>
      </div>

      {/* RIGHT — the agent (intake surface), a fixed full-height rail; actions stream inline in the chat */}
      <aside className="obench-side">
        <AgentChat transcript={sent} lines={lines} running={running} canSend={!running} onSend={create}
          placeholder="Describe the leasing request…" />
      </aside>
    </div>
  );
}
