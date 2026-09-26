"use client";
import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/lib/types";
import type { FeedLine } from "@/components/LiveFeed";

/** Right rail — the single agent surface and the record of the conversation. It shows three kinds of
 *  entry inline: the salesperson's messages/confirmations (what was decided, with an "edited" tag when
 *  the agent's proposal was changed), the agent's replies, and the agent's own working log (engine
 *  steps), rendered Claude-Code-style between the messages. One place, one source of truth. */
export function AgentChat({
  transcript, lines, running, canSend, onSend, placeholder, pendingMessage,
}: {
  transcript: ChatMessage[];
  lines: FeedLine[];
  running: boolean;
  canSend: boolean;
  onSend: (message: string) => void;
  placeholder?: string;
  pendingMessage?: string | null;
}) {
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [transcript, lines, running, pendingMessage]);

  function send() {
    const t = draft.trim();
    if (!t || !canSend) return;
    onSend(t);
    setDraft("");
  }

  const empty = transcript.length === 0 && lines.length === 0 && !running;

  return (
    <div className="panel chat">
      <div className="phead"><h3>Agent</h3>
        <span className="chip acc" style={{ marginLeft: "auto" }}>AI · understands & explains</span>
      </div>
      <div className="pbody chat" style={{ paddingBottom: 12 }}>
        <div className="chatlog" ref={logRef}>
          {empty && (
            <p className="mini faint">Tell me the request in plain language — vehicle, customer, term,
              quantity, budget. I’ll fill the steps on the left; you confirm each one.</p>
          )}
          {transcript.map((m, i) =>
            m.kind === "confirm"
              ? <ConfirmEntry key={i} m={m} />
              : <div key={i} className={`bub ${m.role === "user" ? "u" : "a"}`}>{m.content}</div>
          )}
          {pendingMessage && <div className="bub u">{pendingMessage}</div>}
          {(lines.length > 0 || running) && <AgentLog lines={lines} running={running} />}
        </div>
        <div className="chatin">
          <input className="inp" value={draft} disabled={!canSend || running}
            placeholder={canSend ? (placeholder ?? "Message the agent…") : "Use the panel on the left · click “Adjust” to chat again"}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") send(); }} />
          <button className="btn primary" onClick={send} disabled={!canSend || running || !draft.trim()}>
            {running ? "…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** A human decision recorded from the wizard: what was confirmed, plus an "edited" tag when the
 *  salesperson changed what the agent had proposed. */
function ConfirmEntry({ m }: { m: ChatMessage }) {
  return (
    <div className="cfm">
      <span className="cfm-ic" aria-hidden>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="2,6.5 5,9 10,3" /></svg>
      </span>
      <div className="cfm-body">
        <div className="cfm-top">
          <span className="cfm-title">{m.title ?? m.content}</span>
          {m.edited && <span className="cfm-edited">edited</span>}
        </div>
        {m.detail && <div className="cfm-detail num">{m.detail}</div>}
      </div>
    </div>
  );
}

const BAND_COLOR: Record<string, string> = { GREEN: "var(--green)", YELLOW: "var(--amber)", RED: "var(--rose)" };

/** The agent's working log, Claude-Code-style: a thin guided rail of steps, each a title with an
 *  optional band/detail sub-line, expandable when there's more. Shown inline in the conversation. */
function AgentLog({ lines, running }: { lines: FeedLine[]; running: boolean }) {
  // Drop the "awaiting your input" markers — the wizard/panels already show what's needed; the log is
  // for what the agent DID, not for repeating that it's waiting.
  const shown = lines.filter((l) => !l.await);
  if (shown.length === 0 && !running) return null;
  return (
    <div className="alog">
      {shown.map((l) => <LogRow key={l.id} l={l} />)}
      {running && (
        <div className="lrow">
          <div className="lrow-head"><span className="lrow-dot pulse" style={{ background: "var(--accent)" }} />
            <span className="lrow-lbl faint">Working…</span></div>
        </div>
      )}
    </div>
  );
}

function LogRow({ l }: { l: FeedLine }) {
  const has = !!(l.detail || l.band);
  const [open, setOpen] = useState(false);
  const color = l.error ? "var(--rose)" : l.await ? "var(--amber)" : "var(--accent)";
  return (
    <div className="lrow">
      <button className={`lrow-head ${has ? "exp" : ""}`} onClick={() => has && setOpen((o) => !o)}>
        <span className="lrow-dot" style={{ background: color }} />
        <span className="lrow-lbl">{l.label}</span>
        {l.band && <span className="lrow-band" style={{ color: BAND_COLOR[l.band] ?? "inherit" }}>{l.band}{l.score ? ` · ${l.score}` : ""}</span>}
        {has && <span className="lrow-chev">{open ? "▾" : "▸"}</span>}
      </button>
      {open && l.detail && <div className="lrow-detail num">{l.detail}</div>}
    </div>
  );
}
