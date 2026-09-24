"use client";
import { useEffect, useState } from "react";

export type Actor = "SALES" | "APPROVER";
export const ACTOR_EMAIL: Record<Actor, string> = {
  SALES: "sales@demo.local",
  APPROVER: "approver@demo.local",
};

const KEY = "aoc.actor";
const EVT = "aoc.actorchange";

export function getActor(): Actor {
  if (typeof window === "undefined") return "SALES";
  return (localStorage.getItem(KEY) as Actor) || "SALES";
}

export function setActor(a: Actor) {
  localStorage.setItem(KEY, a);
  window.dispatchEvent(new Event(EVT));
}

export function useActor(): [Actor, (a: Actor) => void] {
  const [actor, set] = useState<Actor>("SALES");
  useEffect(() => {
    set(getActor());
    const h = () => set(getActor());
    window.addEventListener(EVT, h);
    return () => window.removeEventListener(EVT, h);
  }, []);
  return [actor, setActor];
}
