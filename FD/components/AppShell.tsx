"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { ReactNode, useEffect, useState } from "react";
import { initTheme, isDark, toggleTheme } from "@/lib/theme";

/** Product name — single source; change here to rebrand. */
const NAME = "Leasedesk";

const EXPANDED_W = 242;
const RAIL_W = 50;

/** App shell in the reference (SWARION) layout: full-width header with brand cell + centred search,
 *  and a toggle-collapsed icon-rail sidebar built on the reference's framework — primary items,
 *  collapsible sections, a divider, and settings pinned to the bottom. Hand-rolled SVG icons, no lib.
 *
 *  The nav models a typical B2B leasing workflow (originate → qualify → configure → approve →
 *  contract → analyse). Only Dashboard and Audit trail are wired; the rest are placeholders to build
 *  out one by one (marked "soon", non-navigating). */
export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const isOffers = path === "/" || path.startsWith("/offers");
  const isAudit = path.startsWith("/audit");
  const isSettings = path.startsWith("/settings");
  const activeId = isAudit ? "audit" : isSettings ? "settings" : isOffers ? "dashboard" : "";

  const [collapsed, setCollapsed] = useState(false);
  const [dark, setDark] = useState(false);
  const [hov, setHov] = useState<string | null>(null);
  const [openSection, setOpenSection] = useState<string | null>(isAudit ? "governance" : "originate");
  useEffect(() => { initTheme(); setDark(isDark()); }, []);
  useEffect(() => { if (isAudit) setOpenSection("governance"); }, [isAudit]);

  const brandW = collapsed ? RAIL_W : EXPANDED_W;
  const toggle = () => setCollapsed((c) => !c);
  const toggleSection = (id: string) => {
    if (collapsed) { setCollapsed(false); setOpenSection(id); return; }
    setOpenSection((p) => (p === id ? null : id));
  };

  const navStyle = (active: boolean, hovered: boolean): React.CSSProperties => ({
    display: "flex", alignItems: "center", gap: 9,
    padding: collapsed ? 0 : "7px 14px", margin: collapsed ? "2px auto" : "1px 8px",
    width: collapsed ? RAIL_W : "auto", height: collapsed ? 36 : "auto",
    justifyContent: collapsed ? "center" : "flex-start",
    borderRadius: collapsed ? 8 : 7, fontSize: "13.5px", fontWeight: 500,
    color: active ? "var(--accent)" : "var(--ink)", textDecoration: "none",
    background: active ? "var(--accent-tint)" : hovered ? "var(--hover)" : "transparent",
    transition: "background .12s, color .12s", whiteSpace: "nowrap", overflow: "hidden",
    flexShrink: 0, position: "relative", cursor: "pointer",
  });

  const Item = ({ item }: { item: NavItem }) => {
    const active = activeId === item.id;
    const hovered = hov === item.id;
    const inner = (
      <>
        <span style={{ color: active ? "var(--accent)" : "var(--muted)", display: "flex", alignItems: "center", flexShrink: 0 }}><SIWrap>{IC[item.icon]}</SIWrap></span>
        {!collapsed && <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{item.label}</span>}
        {!collapsed && item.soon && <span style={{ marginLeft: "auto", fontSize: 9, fontWeight: 700, letterSpacing: ".4px", textTransform: "uppercase", color: "var(--faint)" }}>soon</span>}
      </>
    );
    const common = {
      style: navStyle(active, hovered),
      title: collapsed ? item.label : item.soon ? "Coming soon" : undefined,
      onMouseEnter: () => setHov(item.id), onMouseLeave: () => setHov(null),
    };
    return item.href
      ? <Link href={item.href} {...common}>{inner}</Link>
      : <button type="button" {...common} onClick={(e) => e.preventDefault()}>{inner}</button>;
  };

  const Divider = () => (
    <div style={{ height: 1, background: "var(--hair)", margin: collapsed ? "6px 10px" : "6px 14px", flexShrink: 0 }} />
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      {/* ── Header ── */}
      <header style={{ height: "var(--hdr)", display: "flex", alignItems: "center",
        borderBottom: "1px solid var(--hair)", background: "var(--surface)", zIndex: 50, flexShrink: 0 }}>
        <div style={{ width: brandW, minWidth: brandW, display: "flex", alignItems: "center",
          gap: collapsed ? 0 : 9, padding: collapsed ? 0 : "0 12px",
          justifyContent: collapsed ? "center" : "flex-start", borderRight: "1px solid var(--hair)",
          height: "100%", overflow: "hidden", flexShrink: 0,
          transition: "width .2s ease, min-width .2s ease, padding .2s ease" }}>
          <BrandMark size={30} />
          {!collapsed && <span style={{ fontSize: 16, fontWeight: 700, whiteSpace: "nowrap", color: "var(--ink)", letterSpacing: "-.01em" }}>{NAME}</span>}
        </div>

        <div style={{ flex: 1, display: "flex", justifyContent: "center", padding: "0 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, background: "var(--surface-2)",
            border: "1px solid var(--hair)", borderRadius: 8, padding: "6px 14px", width: "100%", maxWidth: 500 }}>
            <span style={{ color: "var(--faint)", display: "flex", flexShrink: 0 }}>{IC.search}</span>
            <input placeholder="Search offers, customers, references…" style={{ border: "none", background: "transparent",
              outline: "none", fontFamily: "var(--sans)", fontSize: 13, color: "var(--ink)", width: "100%" }} />
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 16px" }}>
          <button className="iconbtn" title="Toggle theme" aria-label="Toggle theme"
            onClick={() => setDark(toggleTheme())}>{dark ? IC.sun : IC.moon}</button>
          <span style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--accent-soft)",
            color: "var(--accent-text)", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700 }}>SS</span>
        </div>
      </header>

      {/* ── Body ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        <nav style={{ position: "relative", width: brandW, minWidth: brandW, flexShrink: 0, zIndex: 1,
          transition: "width .2s ease, min-width .2s ease" }}>
          <button onClick={toggle} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            style={{ position: "absolute", right: -13, top: 52, width: 26, height: 26, border: "1px solid var(--hair)",
              background: "var(--surface-2)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              borderRadius: 6, color: "var(--faint)", zIndex: 20, boxShadow: "0 1px 4px rgba(0,0,0,0.08)" }}>
            {collapsed ? IC.expand : IC.collapse}
          </button>

          <aside style={{ width: "100%", height: "100%", background: "var(--surface-2)",
            borderRight: "1px solid var(--hair)", display: "flex", flexDirection: "column",
            overflowY: "auto", overflowX: "hidden" }}>
            {/* primary */}
            <div style={{ padding: collapsed ? "6px 0 2px" : "8px 0 2px", flexShrink: 0 }}>
              {PRIMARY.map((it) => <Item key={it.id} item={it} />)}
            </div>

            {/* collapsible sections */}
            {SECTIONS.map((sec) => {
              const isOpen = openSection === sec.id;
              return (
                <div key={sec.id} style={{ padding: "8px 0 2px", flexShrink: 0 }}>
                  {collapsed ? (
                    <div title={sec.label} onClick={() => toggleSection(sec.id)}
                      style={{ display: "flex", alignItems: "center", justifyContent: "center", width: RAIL_W, height: 32,
                        margin: "0 auto", borderRadius: 6, cursor: "pointer", color: "var(--muted)" }}>
                      <SIWrap>{IC[sec.icon]}</SIWrap>
                    </div>
                  ) : (
                    <div onClick={() => toggleSection(sec.id)}
                      style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "0 12px 6px 14px", cursor: "pointer", userSelect: "none" }}>
                      <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".7px", color: "var(--faint)" }}>{sec.label}</span>
                      <span style={{ display: "flex", color: "var(--faint)", transform: isOpen ? "rotate(0deg)" : "rotate(-90deg)", transition: "transform .2s ease" }}>{IC.chevron}</span>
                    </div>
                  )}
                  {!collapsed && isOpen && (
                    <div style={{ overflow: "hidden", animation: "feedIn .18s ease" }}>
                      {sec.items.map((it) => <Item key={it.id} item={it} />)}
                    </div>
                  )}
                </div>
              );
            })}

            <div style={{ flex: 1, minHeight: 12 }} />
            <Divider />
            <div style={{ padding: "2px 0 10px", flexShrink: 0 }}>
              <Item item={SETTINGS} />
            </div>
          </aside>
        </nav>

        <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", overflowY: "auto" }}>
          {children}
        </main>
      </div>
    </div>
  );
}

/* ── Nav model: a typical B2B leasing workflow ── */
type IconKey = keyof typeof IC;
interface NavItem { id: string; label: string; icon: IconKey; href?: string; soon?: boolean }
interface NavSection { id: string; label: string; icon: IconKey; items: NavItem[] }

const PRIMARY: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard", href: "/" },
  { id: "offers", label: "Offers", icon: "offers", soon: true },
  { id: "applications", label: "Applications", icon: "applications", soon: true },
  { id: "contracts", label: "Contracts", icon: "contracts", soon: true },
];

const SECTIONS: NavSection[] = [
  { id: "configure", label: "Catalogue & Pricing", icon: "catalogue", items: [
    { id: "assets", label: "Asset Catalogue", icon: "assets", soon: true },
    { id: "products", label: "Leasing Products", icon: "products", soon: true },
    { id: "residuals", label: "Residual Values", icon: "residual", soon: true },
    { id: "rates", label: "Rate Cards", icon: "rates", soon: true },
  ] },
  { id: "originate", label: "Customers & Risk", icon: "customers", items: [
    { id: "partners", label: "Business Partners", icon: "partner", soon: true },
    { id: "offer-partners", label: "Offer Partners", icon: "partners", soon: true },
    { id: "credit", label: "Credit & Risk", icon: "risk", soon: true },
  ] },
  { id: "governance", label: "Governance", icon: "governance", items: [
    { id: "audit", label: "Audit Trail", icon: "audit", href: "/audit" },
    { id: "approvals", label: "Approvals", icon: "approvals", soon: true },
    { id: "reports", label: "Reports", icon: "reports", soon: true },
  ] },
];

const SETTINGS: NavItem = { id: "settings", label: "Settings", icon: "settings", href: "/settings" };

/* ── Brand mark (matches app/icon.svg / favicon) ── */
function BrandMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" style={{ flexShrink: 0, display: "block" }}>
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <rect x="8" y="8.5" width="12" height="15.5" rx="2.2" fill="#fff" />
      <path d="M11 13.5h6M11 16.5h6M11 19.5h3.5" stroke="var(--accent)" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M23 6.2l.86 2.34L26.2 9.4l-2.34.86L23 12.6l-.86-2.34L19.8 9.4l2.34-.86z" fill="#fff" />
    </svg>
  );
}

/* ── Hand-rolled SVG icons (reference set; stroke 1.7, 18×18 viewBox) ── */
function SIWrap({ children }: { children: ReactNode }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, display: "block" }}>
      {children}
    </svg>
  );
}
const IC = {
  dashboard: <path d="M2.5 7.8L9 2.5L15.5 7.8V15.5H11.5V11H6.5V15.5H2.5V7.8Z" />,
  offers: <><rect x="3.5" y="2.5" width="11" height="13" rx="1.5" /><path d="M6 6h6M6 9h6M6 12h4" /></>,
  applications: <><rect x="4.5" y="3" width="9" height="12.5" rx="1.5" /><path d="M7 3V2h4v1" /><path d="M7 7.5h4M7 10.5h4" /></>,
  contracts: <><path d="M4.5 2.5h5l4 4v9h-9z" /><path d="M9.5 2.5V6.5h4" /><path d="M6.5 12c.8-.9 1.6.6 2.4 0" /></>,
  catalogue: <><rect x="2.5" y="2.5" width="13" height="13" rx="1.8" /><line x1="2.5" y1="7.5" x2="15.5" y2="7.5" /><line x1="7.5" y1="7.5" x2="7.5" y2="15.5" /></>,
  assets: <><path d="M9 2.5l6 3.2v6.6L9 15.5 3 12.3V5.7z" /><path d="M3 5.9L9 9.2 15 5.9M9 9.2v6.1" /></>,
  products: <><path d="M8.7 2.5H14.5V8.3l-6 6a1.4 1.4 0 0 1-2 0L3 10.7a1.4 1.4 0 0 1 0-2z" /><circle cx="11.3" cy="5.7" r="1" /></>,
  residual: <><path d="M2.5 12.5l3.5-3.5 2.5 2.5 5-5.5" /><path d="M14 6v3.5M14 6h-3.5" /></>,
  rates: <><line x1="4" y1="14" x2="14" y2="4" /><circle cx="5.5" cy="5.5" r="1.6" /><circle cx="12.5" cy="12.5" r="1.6" /></>,
  customers: <><circle cx="9" cy="6.5" r="2.8" /><path d="M3 15.5c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" /></>,
  partner: <><rect x="4" y="2.5" width="10" height="13" rx="1" /><path d="M6.5 5.5h1.5M10 5.5h1.5M6.5 8h1.5M10 8h1.5M6.5 10.5h1.5M10 10.5h1.5" /><path d="M7.5 15.5V13h3v2.5" /></>,
  partners: <><circle cx="6.8" cy="6.5" r="2.3" /><path d="M2.8 14.8c0-2.3 1.8-3.9 4-3.9s4 1.6 4 3.9" /><path d="M11.5 4.6a2.3 2.3 0 0 1 0 4.4" /><path d="M12.2 11c1.8.3 3.3 1.7 3.3 3.8" /></>,
  risk: <><path d="M9 2.5l5 2v3.9c0 3.2-2.1 5.4-5 6.6-2.9-1.2-5-3.4-5-6.6V4.5z" /><path d="M6.8 8.8l1.6 1.6 3-3.4" /></>,
  governance: <><path d="M9 3v11.5" /><path d="M4.5 5.5h9" /><path d="M4.5 5.5L3 9.3h3zM13.5 5.5L12 9.3h3z" /><path d="M6.5 14.5h5" /></>,
  audit: <><path d="M2 4.5h14M2 9h14M2 13.5h9" /><circle cx="14" cy="13.5" r="1.5" /></>,
  approvals: <><circle cx="9" cy="9" r="6.5" /><path d="M6 9l2 2 4-4.5" /></>,
  reports: <><path d="M4 15.5V6M9 15.5V2.5M14 15.5V9" /><line x1="2" y1="15.5" x2="16" y2="15.5" /></>,
  settings: <><circle cx="9" cy="9" r="2.5" /><path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.6 3.6l1.5 1.5M12.9 12.9l1.5 1.5M3.6 14.4l1.5-1.5M12.9 5.1l1.5-1.5" /></>,
  chevron: <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}><path d="M2 3.5L5 6.5L8 3.5" /></svg>,
  search: <svg width="14" height="14" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.8" style={{ display: "block" }}><circle cx="5.5" cy="5.5" r="4" /><line x1="8.5" y1="8.5" x2="12" y2="12" /></svg>,
  collapse: <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}><path d="M8 2L3.5 6.5L8 11" /><path d="M12 2L7.5 6.5L12 11" /></svg>,
  expand: <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}><path d="M5 2L9.5 6.5L5 11" /><path d="M1 2L5.5 6.5L1 11" /></svg>,
  moon: <svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}><path d="M14.5 9.5A5.5 5.5 0 1 1 8.5 3.5a4.3 4.3 0 0 0 6 6Z" /></svg>,
  sun: <svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}><circle cx="9" cy="9" r="3.2" /><path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.8 3.8l1.4 1.4M12.8 12.8l1.4 1.4M3.8 14.2l1.4-1.4M12.8 5.2l1.4-1.4" /></svg>,
};
