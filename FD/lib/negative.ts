import type { ExceptionRow } from "./types";

/** Negative-workflow copy (spec §10.2, FR-62): every blocked/exception state names WHAT happened,
 *  WHY, and WHAT is required next. Keyed by the engine's exception codes. */
export interface NegMessage { what: string; why: string; next: string; }

const MAP: Record<string, NegMessage> = {
  DATA_MISSING: {
    what: "Required information is missing.",
    why: "A mandatory field for this offer has not been provided.",
    next: "Add the missing detail with the agent, then re-price.",
  },
  TERM_OUT_OF_RANGE: {
    what: "The term is outside the allowed range.",
    why: "The product permits 12–60 months for this configuration.",
    next: "Give the agent a term within range to re-price.",
  },
  MILEAGE_OUT_OF_RANGE: {
    what: "The annual mileage is outside policy.",
    why: "The product caps annual mileage for this configuration.",
    next: "Lower the annual mileage, then re-price.",
  },
  SPECIAL_PAYMENT_HIGH: {
    what: "The special payment is high.",
    why: "It exceeds the standard share of the vehicle price and needs review.",
    next: "Reduce the special payment, or proceed to human review.",
  },
  SPECIAL_PAYMENT_TOO_HIGH: {
    what: "The special payment is too high.",
    why: "It is above 30% of the vehicle price, so the offer cannot be priced.",
    next: "Lower the special payment with the agent, then re-price.",
  },
  PRODUCT_INELIGIBLE: {
    what: "This combination isn’t eligible.",
    why: "The selected asset/term/mileage doesn’t meet the product conditions.",
    next: "Change the asset or terms with the agent to find an eligible combination.",
  },
  RISK_YELLOW: {
    what: "Scoring returned Yellow.",
    why: "The risk factors put this offer in the Yellow band — it needs a human decision.",
    next: "Review the risk factors below, then confirm at the review step or adjust.",
  },
  SCORING_MANUAL_REVIEW: {
    what: "Scoring needs manual review.",
    why: "The parameters fall outside the automatic-scoring envelope (exposure, quantity or price).",
    next: "Proceed to human review, or reduce quantity/price to score automatically.",
  },
  ASSESSMENT_UNAVAILABLE: {
    what: "Asset assessment is unavailable.",
    why: "The assessment service for this asset couldn’t be reached, so the offer can’t proceed.",
    next: "Try a different asset with the agent, or retry later.",
  },
  RISK_RED: {
    what: "Scoring returned Red.",
    why: "The offer is Red on affordability/exposure and can’t proceed on the normal path.",
    next: "Try a cheaper vehicle, a shorter term, a higher special payment, or a smaller quantity.",
  },
  SANCTIONS_MATCH: {
    what: "A sanctions match was found.",
    why: "The customer matched a sanctions screening and cannot be offered a lease.",
    next: "This offer can’t proceed. Escalate per compliance; a new variant won’t clear it.",
  },
  KYC_FAILED: {
    what: "KYC could not be completed.",
    why: "Identity / KYC verification for the customer failed.",
    next: "Resolve KYC for the customer before a new offer can proceed.",
  },
  CALCULATION_FAILED: {
    what: "The calculation couldn’t complete.",
    why: "Required inputs for pricing weren’t available.",
    next: "Complete the request with the agent, then re-price.",
  },
  EXTERNAL_SERVICE_UNAVAILABLE: {
    what: "A required service was unavailable.",
    why: "An external dependency for this offer couldn’t be reached.",
    next: "Retry shortly, or adjust the request with the agent.",
  },
};

export function humanizeException(e: ExceptionRow): NegMessage {
  const base = MAP[e.code];
  if (base) return base;
  return {
    what: e.code.replaceAll("_", " ").toLowerCase(),
    why: (e.detail?.reason as string) ?? "This condition needs attention before the offer can proceed.",
    next: e.next_action ? e.next_action.replaceAll("_", " ") : "Resolve it with the agent, then continue.",
  };
}

/** A compliance/terminal block cannot be fixed by editing terms — it needs a new offer or escalation. */
export function isTerminalBlock(code: string): boolean {
  return ["SANCTIONS_MATCH", "KYC_FAILED", "RISK_RED"].includes(code);
}
