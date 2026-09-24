"use client";
import { useState } from "react";
import type { CatalogueVehicle } from "@/lib/types";
import { carImage } from "@/lib/carImage";
import { eur } from "@/lib/format";

const FUEL: Record<string, string> = { PETROL: "Petrol", DIESEL: "Diesel", ELECTRIC: "Electric" };

function Car() {
  return (
    <svg className="w-[82%] max-w-[340px]" viewBox="0 0 340 150" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M20 108 Q22 96 40 92 L92 84 Q112 60 150 56 L232 56 Q262 58 286 84 L312 92 Q326 96 328 108 L328 118 Q328 122 322 122 L26 122 Q20 122 20 118 Z" fill="var(--hair)" />
      <path d="M104 84 Q120 64 150 62 L200 62 Q206 74 208 84 Z" fill="color-mix(in srgb,var(--surface) 70%,var(--hair))" />
      <path d="M212 84 Q210 70 226 64 Q252 66 274 84 Z" fill="color-mix(in srgb,var(--surface) 70%,var(--hair))" />
      <circle cx="86" cy="120" r="20" fill="var(--ink)" opacity=".75" /><circle cx="86" cy="120" r="9" fill="var(--faint)" />
      <circle cx="266" cy="120" r="20" fill="var(--ink)" opacity=".75" /><circle cx="266" cy="120" r="9" fill="var(--faint)" />
    </svg>
  );
}

export function VehicleCard({
  vehicle, colour, onColour,
}: { vehicle: CatalogueVehicle; colour?: string | null; onColour?: (c: string) => void }) {
  const [broken, setBroken] = useState(false);
  const img = carImage(vehicle.make, vehicle.model_family || vehicle.commercial_name);
  const specs: [string, string][] = [
    ["Fuel", FUEL[vehicle.fuel_type || ""] || vehicle.fuel_type || "—"],
    ["Transmission", vehicle.transmission || "—"],
    ["Power", vehicle.engine_power_hp ? `${vehicle.engine_power_hp} hp · ${vehicle.engine_power_kw} kW` : "—"],
    ["Engine", vehicle.engine_capacity_cc ? `${vehicle.engine_capacity_cc} cc` : vehicle.fuel_type === "ELECTRIC" ? "EV" : "—"],
    ["Body / Seats", `${vehicle.body_type || "—"}${vehicle.seats ? ` · ${vehicle.seats}` : ""}`],
    ["CO₂", vehicle.wltp_co2_g_km != null ? `${vehicle.wltp_co2_g_km} g/km${vehicle.co2_class ? ` · class ${vehicle.co2_class}` : ""}` : "—"],
  ];
  return (
    <div className="panel" style={{ overflow: "hidden" }}>
      <div className="vhero">
        <div className="vpic">
          <span className="tag">vehicle photo · live from car-image API</span>
          {img && !broken
            ? /* eslint-disable-next-line @next/next/no-img-element */
              <img src={img} alt={vehicle.label} onError={() => setBroken(true)} loading="lazy" />
            : <Car />}
        </div>
        <div style={{ padding: 16 }}>
          <div className="text-[15px] font-semibold">{vehicle.make} {vehicle.commercial_name}</div>
          <div className="mini muted">{vehicle.variant}</div>
          <div className="specgrid">
            {specs.map(([k, v]) => (<div key={k}><div className="k">{k}</div><div className="v num">{v}</div></div>))}
            <div><div className="k">List price (net)</div><div className="v num">{eur(vehicle.list_price_net)}</div></div>
          </div>
          {vehicle.colours && vehicle.colours.length > 0 && (
            <>
              <div className="mini faint" style={{ marginTop: 12 }}>Colour</div>
              <div className="sw">
                {vehicle.colours.map((c) => {
                  const active = (colour ?? vehicle.colours?.[0]) === c;
                  return (
                    <button key={c} type="button" className={active ? "on" : ""} onClick={() => onColour?.(c)}
                      disabled={!onColour} style={{ cursor: onColour ? "pointer" : "default" }}>{c}</button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
