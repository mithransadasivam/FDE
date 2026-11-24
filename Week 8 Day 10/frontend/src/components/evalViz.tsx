// Small charts for the Evaluation screen: a Pareto chart, a 2×2 agreement matrix, and a page crop.
import type { Agreement, TaxonomyRow } from "../api";

export function Pareto({ rows, testId }: { rows: TaxonomyRow[]; testId?: string }) {
  const W = 560, H = 230, L = 34, B = 48, T = 14;
  const max = Math.max(1, ...rows.map((r) => r.count));
  const bw = rows.length ? (W - L - 10) / rows.length : 0;
  const y = (v: number) => T + (H - T - B) * (1 - v);
  const pts = rows.map((r, i) => `${L + i * bw + bw / 2},${y(r.cumulative / 100)}`).join(" ");
  return (
    <svg data-testid={testId} viewBox={`0 0 ${W} ${H}`} className="w-full">
      {[0, 0.5, 1].map((g) => <line key={g} x1={L} x2={W - 6} y1={y(g)} y2={y(g)} stroke="#E6E8F0" />)}
      <text x={L - 6} y={y(1) + 4} textAnchor="end" fontSize="10" fill="#9A9EB3">{max}</text>
      <text x={W - 4} y={y(0.8) - 4} textAnchor="end" fontSize="10" fill="#E8552F">80%</text>
      <line x1={L} x2={W - 6} y1={y(0.8)} y2={y(0.8)} stroke="#E8552F" strokeDasharray="4 4" strokeWidth="1" />
      {rows.map((r, i) => {
        const h = (H - T - B) * (r.count / max);
        const x = L + i * bw + bw * 0.15;
        return (
          <g key={r.type}>
            <rect x={x} y={y(0) - h} width={bw * 0.7} height={h} rx="4" fill={i < 2 ? "#1B1F3B" : "#B7BCD0"} />
            <text x={x + bw * 0.35} y={y(0) - h - 5} textAnchor="middle" fontSize="12" fontWeight="600" fill="#1B1F3B">{r.count}</text>
            <text x={x + bw * 0.35} y={H - B + 16} textAnchor="middle" fontSize="10.5" fill="#5E6378">{r.type.replace(/_/g, " ").slice(0, 18)}</text>
            <text x={x + bw * 0.35} y={H - B + 30} textAnchor="middle" fontSize="10" fill="#9A9EB3">{r.share}%</text>
          </g>
        );
      })}
      {rows.length > 1 && <polyline points={pts} fill="none" stroke="#0E8F7E" strokeWidth="2" />}
      {rows.map((r, i) => <circle key={r.type} cx={L + i * bw + bw / 2} cy={y(r.cumulative / 100)} r="3.5" fill="#0E8F7E" />)}
    </svg>
  );
}

export function Matrix({ a, rater, expert, pos, neg, testId }: { a: Agreement; rater: string; expert: string; pos: string; neg: string; testId?: string }) {
  const cell = (n: number, good: boolean, label: string) => (
    <div className={`rounded-lg px-3 py-2 ${good ? "bg-teal-50" : n ? "bg-ember-50" : "bg-mist"}`}>
      <div className={`text-[20px] font-semibold leading-none ${good ? "text-teal" : n ? "text-ember" : "text-ink-3"}`}>{n}</div>
      <div className="mt-1 text-[11px] text-ink-2">{label}</div>
    </div>
  );
  return (
    <div data-testid={testId} className="grid grid-cols-[90px_1fr_1fr] gap-1.5 text-[11.5px]">
      <div />
      <div className="text-center font-semibold text-ink-2">{expert}: {pos}</div>
      <div className="text-center font-semibold text-ink-2">{expert}: {neg}</div>
      <div className="self-center font-semibold text-ink-2">{rater}: {pos}</div>
      {cell(a.tp, true, "both: problem")}
      {cell(a.fp, false, `${rater} only`)}
      <div className="self-center font-semibold text-ink-2">{rater}: {neg}</div>
      {cell(a.fn, false, `${expert} only`)}
      {cell(a.tn, true, "both: fine")}
    </div>
  );
}

/** A crop of the page around a field box, from the document image (850 × 1100). */
export function PageCrop({ image, box, width = 300 }: { image: string; box: [number, number, number, number] | null; width?: number }) {
  if (!box) return <div className="grid place-items-center rounded-lg bg-mist text-[11px] text-ink-3" style={{ width, height: 70 }}>no box</div>;
  const pad = 0.03;
  const x0 = Math.max(0, box[0] - pad), x1 = Math.min(1, box[2] + pad);
  const rw = Math.max(0.3, x1 - x0);
  const cx0 = Math.min(x0, 1 - rw);
  // pick a height, then the page region that fills it exactly (the image keeps its 850 × 1100 shape)
  const want = ((box[3] - box[1]) + 0.05) * 1100 * width / (rw * 850);
  const height = Math.max(56, Math.min(130, want));
  const rh = (height * rw * 850) / (width * 1100);
  const y0 = Math.min(Math.max(0, (box[1] + box[3]) / 2 - rh / 2), 1 - rh);
  return (
    <div className="relative overflow-hidden rounded-lg border border-black/10 bg-white" style={{ width, height }}>
      <div className="absolute inset-0" style={{
        backgroundImage: `url(${image})`, backgroundSize: `${100 / rw}% auto`,
        backgroundPosition: `${(cx0 / (1 - rw)) * 100}% ${(y0 / Math.max(0.0001, 1 - rh)) * 100}%`,
      }} />
      <div className="absolute rounded-[2px] border-2 border-amber" style={{
        left: `${((box[0] - cx0) / rw) * 100}%`, width: `${((box[2] - box[0]) / rw) * 100}%`,
        top: `${((box[1] - y0) / rh) * 100}%`, height: `${((box[3] - box[1]) / rh) * 100}%`,
      }} />
    </div>
  );
}
