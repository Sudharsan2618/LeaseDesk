// FINN-style vehicle imagery via a public car-image CDN (IMAGIN.studio demo tier).
// Renders a studio image by make + model family + angle; falls back to null when unknown.
const CUSTOMER = process.env.NEXT_PUBLIC_IMAGIN_CUSTOMER || "hrjavascript-mastery";

export function carImage(
  make?: string | null,
  modelFamily?: string | null,
  opts: { angle?: number; width?: number; paint?: string } = {},
): string | null {
  if (!make || !modelFamily) return null;
  const p = new URLSearchParams({
    customer: CUSTOMER,
    make: make.toLowerCase(),
    modelFamily: modelFamily.toLowerCase().split(" ")[0],
    angle: String(opts.angle ?? 23),
    width: String(opts.width ?? 720),
    zoomType: "fullscreen",
  });
  if (opts.paint) p.set("paintDescription", opts.paint);
  return `https://cdn.imagin.studio/getimage?${p.toString()}`;
}
