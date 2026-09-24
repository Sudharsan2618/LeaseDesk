"use client";
import { useRef, useState } from "react";
import { streamPost } from "./api";
import type { Snapshot } from "./types";
import type { FeedLine } from "@/components/LiveFeed";

export function useOfferStream() {
  const [lines, setLines] = useState<FeedLine[]>([]);
  const [running, setRunning] = useState(false);
  const idRef = useRef(0);

  const add = (l: Omit<FeedLine, "id">) =>
    setLines((prev) => [...prev, { id: idRef.current++, ...l }]);

  async function run(path: string, body: unknown): Promise<Snapshot | null> {
    setRunning(true);
    let snap: Snapshot | null = null;
    try {
      await streamPost(path, body, (e) => {
        if (e.kind === "node")
          add({ label: e.label ?? e.node ?? "…", band: e.band, score: e.score, detail: e.detail });
        else if (e.kind === "await") add({ label: e.label ?? "Awaiting your input", await: true });
        else if (e.kind === "snapshot") snap = e.snapshot ?? null;
        else if (e.kind === "error") add({ label: e.detailText ?? "Something went wrong", error: true });
      });
    } catch (err) {
      add({ label: (err as Error).message, error: true });
    }
    setRunning(false);
    return snap;
  }

  return { lines, running, run, reset: () => setLines([]) };
}
