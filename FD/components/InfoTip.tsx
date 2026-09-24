"use client";
/** A small ⓘ affordance that reveals grounded explanation on hover/focus — used to tuck the AI
 *  explanation into the section it explains (e.g. Pricing & scenarios) instead of a standalone panel. */
export function InfoTip({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <span className="tipwrap">
      <button className="tipbtn" aria-label={title ?? "Explanation"} tabIndex={0}>i</button>
      <span className="tippop" role="tooltip">
        {title && <b className="tiptitle">{title}</b>}
        {children}
      </span>
    </span>
  );
}
