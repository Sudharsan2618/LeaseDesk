"use client";

const KEY = "aoc.theme";

export function initTheme() {
  try {
    const t = localStorage.getItem(KEY);
    if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t);
  } catch {}
}

export function isDark(): boolean {
  const r = document.documentElement;
  const attr = r.getAttribute("data-theme");
  if (attr) return attr === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function toggleTheme(): boolean {
  const next = isDark() ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem(KEY, next); } catch {}
  return next === "dark";
}
