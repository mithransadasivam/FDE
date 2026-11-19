import { useEffect, useState } from "react";
import { api, type CostResult } from "../../api";
import { Card, Kpi } from "../../components/ui";

const PART = { model: { label: "Model", c: "#5B6BBF" }, ocr: { label: "OCR", c: "#30365E" }, api: { label: "Public API", c: "#E8552F" }, platform: { label: "Platform (fixed)", c: "#C9CCE3" } } as const;
const LINE: Record<string, string> = { A: "#5B6BBF", B: "#0E8F7E", C: "#E8552F" };
const gbp = (n: number) => `£${n.toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

function Bars({ data }: { data: CostResult }) {
  const max = Math.max(...data.options.map((o) => o.total_gbp)) * 1.15;
  return (
    <svg data-testid="cost-bars" viewBox="0 0 520 230" className="w-full">
      {data.options.map((o, i) => {
        let x = 120;
        return (
          <g key={o.id} data-testid={`bar-${o.id}`}>
            <text x={112} y={42 + i * 62} textAnchor="end" fontSize="12" fontWeight="700" fill="#1B1F3B">Option {o.id}</text>
            <text x={112} y={57 + i * 62} textAnchor="end" fontSize="10" fill="#5E6378">{o.name}</text>
            {(Object.keys(PART) as (keyof typeof PART)[]).map((k) => {
              const w = ((o.parts[k] ?? 0) / max) * 360;
              const r = <rect key={k} x={x} y={28 + i * 62} width={w} height={30} fill={PART[k].c} />;
              x += w;
              return r;
            })}
            <text x={x + 8} y={48 + i * 62} fontSize="13" fontWeight="700" fill="#1B1F3B">{gbp(o.total_gbp)}</text>
          </g>
        );
      })}
      {(Object.keys(PART) as (keyof typeof PART)[]).map((k, i) => (
        <g key={k}><rect x={120 + i * 100} y={212} width={10} height={10} fill={PART[k].c} /><text x={134 + i * 100} y={221} fontSize="10" fill="#5E6378">{PART[k].label}</text></g>
      ))}
    </svg>
  );
}

function Curve({ data }: { data: CostResult }) {
  const W = 520, H = 250, L = 56, B = 34, T = 12, R = 14;
  const xs = data.curve.map((p) => p.docs);
  const ids = data.options.map((o) => o.id);
  const ymax = Math.ceil((Math.max(...data.curve.flatMap((p) => ids.map((id) => p[id]))) * 1.05) / 250) * 250;
  const lx = (v: number) => L + (Math.log10(v) - Math.log10(xs[0])) / (Math.log10(xs[xs.length - 1]) - Math.log10(xs[0])) * (W - L - R);
  const ly = (v: number) => H - B - (v / ymax) * (H - B - T);
  const now = data.inputs.docs;
  return (
    <svg data-testid="cost-curve" viewBox={`0 0 ${W} ${H}`} className="w-full">
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <g key={f}><line x1={L} x2={W - R} y1={ly(ymax * f)} y2={ly(ymax * f)} stroke="#EEF0F5" />
          <text x={L - 6} y={ly(ymax * f) + 3} textAnchor="end" fontSize="9.5" fill="#9A9EB3">{gbp(ymax * f)}</text></g>
      ))}
      {[1000, 5000, 10000, 50000, 100000].map((v) => <text key={v} x={lx(v)} y={H - B + 14} textAnchor="middle" fontSize="9.5" fill="#9A9EB3">{v >= 1000 ? `${v / 1000}k` : v}</text>)}
      <text x={(W + L) / 2} y={H - 4} textAnchor="middle" fontSize="10.5" fontWeight="600" fill="#5E6378">Documents a month (log scale)</text>
      <line x1={lx(now)} x2={lx(now)} y1={T} y2={H - B} stroke="#1B1F3B" strokeDasharray="4 3" />
      <text x={lx(now) - 4} y={H - B - 6} textAnchor="end" fontSize="10" fontWeight="700" fill="#1B1F3B">now</text>
      <line x1={lx(now * 2)} x2={lx(now * 2)} y1={T} y2={H - B} stroke="#D98E04" strokeDasharray="4 3" />
      <text x={lx(now * 2) + 4} y={H - B - 6} fontSize="10" fontWeight="700" fill="#D98E04">×2 peak</text>
      {ids.map((id) => (
        <g key={id} data-testid={`curve-${id}`}>
          <polyline fill="none" stroke={LINE[id] ?? "#9A9EB3"} strokeWidth="2.5" points={data.curve.map((p) => `${lx(p.docs)},${ly(p[id])}`).join(" ")} />
          <rect x={L + 10 + ids.indexOf(id) * 78} y={T + 2} width={12} height={4} rx="2" fill={LINE[id] ?? "#9A9EB3"} />
          <text x={L + 26 + ids.indexOf(id) * 78} y={T + 8} fontSize="10.5" fontWeight="700" fill={LINE[id] ?? "#9A9EB3"}>Option {id}</text>
        </g>
      ))}
    </svg>
  );
}

export default function CostTab() {
  const [docs, setDocs] = useState(8600);
  const [pages, setPages] = useState(1.4);
  const [mins, setMins] = useState(3);
  const [data, setData] = useState<CostResult | null>(null);
  useEffect(() => {
    const t = setTimeout(() => api.get<CostResult>(`/api/design/cost?docs=${docs}&pages=${pages}&minutes_saved=${mins}`).then(setData), 150);
    return () => clearTimeout(t);
  }, [docs, pages, mins]);
  if (!data) return null;
  const cheapest = [...data.options].sort((a, b) => a.total_gbp - b.total_gbp)[0];
  const ab = data.options.filter((o) => o.id !== "C");
  return (
    <div>
      <div className="grid grid-cols-[320px_1fr] gap-4">
        <Card className="p-4">
          <div className="text-[14px] font-semibold">Volumes and assumptions</div>
          {[
            { label: "Proof-of-address documents a month", v: docs, set: setDocs, min: 1000, max: 100000, step: 100, fmt: (n: number) => n.toLocaleString("en-GB"), id: "docs" },
            { label: "Pages per document", v: pages, set: setPages, min: 1, max: 3, step: 0.1, fmt: (n: number) => n.toFixed(1), id: "pages" },
            { label: "Analyst minutes saved per document", v: mins, set: setMins, min: 0, max: 6, step: 0.5, fmt: (n: number) => n.toFixed(1), id: "mins" },
          ].map((s) => (
            <label key={s.id} className="mt-4 block">
              <div className="flex justify-between text-[12px]"><span className="text-ink-2">{s.label}</span><b data-testid={`val-${s.id}`}>{s.fmt(s.v)}</b></div>
              <input data-testid={`in-${s.id}`} type="range" min={s.min} max={s.max} step={s.step} value={s.v} onChange={(e) => s.set(Number(e.target.value))} className="mt-1 w-full accent-teal" />
            </label>
          ))}
          <div className="mt-4 flex gap-2">
            <button onClick={() => setDocs(8600)} className="rounded-md border border-black/10 px-2 py-1 text-[11.5px]">Today: 8,600</button>
            <button data-testid="peak" onClick={() => setDocs(17200)} className="rounded-md border border-amber px-2 py-1 text-[11.5px] text-amber">January peak: 17,200</button>
          </div>
          <div className="mt-4 rounded-lg bg-mist p-3 text-[11.5px] leading-snug text-ink-2">
            Prices come from <b>data/Day02_Slide21_price_sheet.csv</b>, with their source and date. Model prices include the 10% premium for a regional (UK) endpoint.
          </div>
        </Card>
        <div className="grid grid-cols-3 content-start gap-3">
          <Kpi label="Cheapest option" value={`Option ${cheapest.id}`} sub={`${gbp(cheapest.total_gbp)} a month at this volume`} />
          <Kpi label="A vs B" value={gbp(Math.abs(ab[0]?.total_gbp - (ab[1]?.total_gbp ?? 0)))} sub={`a month, ${ab[0] && ab[1] && ab[0].total_gbp < ab[1].total_gbp ? "A" : "B"} is cheaper`} tone="teal" />
          <Kpi label="Value of analyst time saved" value={<span data-testid="value">{gbp(data.value_gbp)}</span>} sub="a month: documents × minutes saved × cost per minute" tone="amber" />
          <Card className="col-span-3 p-4">
            <div className="grid grid-cols-2 gap-6">
              <div><div className="text-[13px] font-semibold">Monthly run-cost at {docs.toLocaleString("en-GB")} documents</div><Bars data={data} /></div>
              <div><div className="text-[13px] font-semibold">How cost grows with volume</div><Curve data={data} /></div>
            </div>
          </Card>
        </div>
      </div>
      <Card className="mt-4 overflow-hidden">
        <table className="w-full text-left text-[12px]" data-testid="prices">
          <thead className="bg-mist text-[11px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-2">Price</th><th className="px-3">Value</th></tr></thead>
          <tbody>{Object.entries(data.prices).map(([k, v]) => <tr key={k} className="border-t border-black/[0.05]"><td className="px-4 py-1.5">{k}</td><td className="px-3 tabular-nums">{v}</td></tr>)}</tbody>
        </table>
      </Card>
    </div>
  );
}
