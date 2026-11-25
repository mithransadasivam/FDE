// Cascade (Activity 3, ticket ENG-1103): the small model reads every document; the pilot (ADR-003) reads the ones it is
// not sure of. The cascade must let through no more errors than the pilot alone.
import { Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type CascadeResult } from "../../api";
import { Button, Card, Chip, Kpi } from "../../components/ui";
import { FIELD_NAMES, ModelPicker, TicketChips11, useDistil } from "./parts";

const CHOICES = [0.6, 0.7, 0.8, 0.9];

function Curve({ r }: { r: CascadeResult }) {
  const W = 520, H = 240, L = 44, B = 36, T = 14, R = 16;
  const maxY = Math.max(16, ...r.curve.map((p) => p.slipped), r.pilot.slipped + 2);
  const x = (v: number) => L + v * (W - L - R);
  const y = (v: number) => T + (1 - v / maxY) * (H - T - B);
  return (
    <svg width={W} height={H} data-testid="cascade-curve" className="overflow-visible">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => <g key={v}><line x1={x(v)} x2={x(v)} y1={T} y2={H - B} stroke="#E6E8EF" /><text x={x(v)} y={H - B + 14} fontSize="10" textAnchor="middle" fill="#6B7090">{Math.round(v * 100)}%</text></g>)}
      {[0, 5, 10, 15, 20, 30, 40, 50].filter((v) => v <= maxY).map((v) => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="#E6E8EF" /><text x={L - 6} y={y(v) + 3} fontSize="10" textAnchor="end" fill="#6B7090">{v}</text></g>)}
      <text x={(L + W - R) / 2} y={H - 4} fontSize="10.5" textAnchor="middle" fill="#40456A">Documents sent to the pilot</text>
      <text x={12} y={(T + H - B) / 2} fontSize="10.5" textAnchor="middle" fill="#40456A" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>Errors that slip through</text>
      <line x1={L} x2={W - R} y1={y(r.pilot.slipped)} y2={y(r.pilot.slipped)} stroke="#D98E04" strokeDasharray="5 4" />
      <text x={W - R} y={y(r.pilot.slipped) + 15} fontSize="10.5" textAnchor="end" fill="#D98E04" fontWeight="600">the pilot alone: {r.pilot.slipped}</text>
      <polyline fill="none" stroke="#0E8F7E" strokeWidth="2" points={r.curve.map((p) => `${x(p.teacher_share)},${y(p.slipped)}`).join(" ")} />
      {r.curve.map((p) => {
        const now = Math.abs(p.threshold - r.threshold) < 1e-9;
        return <g key={p.threshold}><circle cx={x(p.teacher_share)} cy={y(p.slipped)} r={now ? 6 : 3.5} fill={now ? "#0E8F7E" : "#fff"} stroke="#0E8F7E" strokeWidth="2" />
          {[0.5, 0.6, 0.7, 0.8, 0.9, 0.95].includes(p.threshold) && <text x={x(p.teacher_share) + 6} y={y(p.slipped) - 7} fontSize="10" fill="#0E8F7E">{p.threshold.toFixed(2)}</text>}</g>;
      })}
    </svg>
  );
}

export default function CascadeTab() {
  const { st } = useDistil();
  const [model, setModel] = useState<string | null>(null);
  const [th, setTh] = useState<number | null>(null);
  const [r, setR] = useState<CascadeResult | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (st && !model) { setModel(st.active); setTh(st.threshold); } }, [st]);
  const run = async (t = th) => {
    if (!model || t === null) return;
    setBusy(true);
    try { setR(await api.post<CascadeResult>("/api/distil/cascade", { model, set: "october", threshold: t, spot: 5 })); }
    finally { setBusy(false); }
  };
  useEffect(() => { if (model && th !== null) run(th); }, [model]);
  if (!st) return null;
  const better = r && r.slipped <= r.pilot.slipped;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><TicketChips11 st={st} /><span className="ml-auto text-[12px] text-ink-3">Model</span><ModelPicker st={st} value={model} onChange={setModel} /></div>
      <Card className="flex items-center gap-3 p-3">
        <span className="text-[12.5px] font-semibold">A field is sure enough from</span>
        {CHOICES.map((c) => (
          <button key={c} data-testid={`th-${c}`} onClick={() => { setTh(c); run(c); }}
            className={`rounded-lg px-2.5 py-1.5 font-mono text-[12.5px] font-semibold ${th === c ? "bg-navy text-white" : "bg-mist text-ink-2 hover:bg-black/10"}`}>{c.toFixed(2)}</button>
        ))}
        <span className="text-[12px] text-ink-3">· the October batch, 200 documents · 1 in 20 confident documents is spot-checked by the pilot</span>
        <span className="ml-auto"><Button testId="run-cascade" onClick={() => run()} disabled={busy || !model}>{busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Run the cascade</Button></span>
      </Card>
      {r && r.model && (
        <>
          <div className="grid grid-cols-5 gap-3" data-testid="cascade-kpis">
            <Kpi label="Errors that slip through" value={<span data-testid="slipped">{r.slipped}</span>} sub={`the pilot alone: ${r.pilot.slipped} · from the small model: ${r.slipped_small}`} tone={better ? "teal" : "ember"} />
            <Kpi label="Read by the small model alone" value={<span data-testid="small-docs">{r.small_docs - r.spot_checks}</span>} sub={`of ${r.documents} documents`} tone="teal" />
            <Kpi label="Sent to the pilot" value={<span data-testid="teacher-share">{Math.round(100 * r.teacher_share)}%</span>} sub={`${r.teacher_docs} unsure + ${r.spot_checks} spot checks · ${r.sonnet_calls} Sonnet calls (pilot alone: ${r.pilot.sonnet_calls})`} />
            <Kpi label="Fields to a person" value={`${r.to_person_pct}%`} sub={`the pilot alone: ${r.pilot.to_person_pct}%`} tone="teal" />
            <Kpi label="Spot checks agree" value={`${r.spot_agree} of ${r.spot_fields}`} sub="fields, small model and pilot" />
          </div>
          <div className="grid grid-cols-[560px_1fr] gap-4">
            <Card className="p-4"><div className="mb-2 text-[13px] font-semibold">Every threshold, from the same run</div><Curve r={r} />
              <div className="mt-2 text-[12px] text-ink-2">Lower thresholds keep more documents on the small model; past a point, its errors slip through.</div></Card>
            <div className="space-y-4">
              <Card className="p-4" testId="cascade-reasons">
                <div className="text-[13px] font-semibold">Why documents went to the pilot at {r.threshold.toFixed(2)}</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {Object.entries(r.reasons).sort((a, b) => b[1] - a[1]).map(([k, n]) => <Chip key={k} tone="amber">{FIELD_NAMES[k.split(" ")[0]] ?? k} {k.split(" ")[1]} · {n}</Chip>)}
                  {!Object.keys(r.reasons).length && <span className="text-[12px] text-ink-3">None</span>}
                </div>
                <div className="mt-3 max-h-[150px] overflow-y-auto text-[11.5px]">
                  {r.rows.filter((x) => x.route === "teacher").slice(0, 30).map((x) => (
                    <div key={x.doc_id} className="flex gap-2 border-t border-black/[0.04] py-1"><span className="w-12 font-mono font-semibold">{x.doc_id}</span><span className="text-ink-2">{x.reasons.join(" · ")}</span></div>
                  ))}
                </div>
              </Card>
              <Card className="overflow-hidden" testId="slipped-list">
                <div className="px-4 py-2 text-[13px] font-semibold">Errors that slipped through ({r.slipped})</div>
                <table className="w-full text-[11.5px]">
                  <thead className="bg-mist text-left text-[10px] uppercase tracking-wide text-ink-3"><tr><th className="px-3 py-1">Document</th><th>Field</th><th>Value</th><th>Tom's label</th><th className="px-3">Read by</th></tr></thead>
                  <tbody>{r.slipped_items.slice(0, 16).map((s) => (
                    <tr key={s.doc_id + s.name} className="border-t border-black/[0.05]"><td className="px-3 py-1 font-mono">{s.doc_id}</td><td>{FIELD_NAMES[s.name]}</td>
                      <td className="font-mono">{s.value}</td><td className="font-mono">{s.expected}</td><td className="px-3"><Chip tone={s.how === "small" ? "ember" : "amber"}>{s.how === "small" ? "small model" : "pilot"}</Chip></td></tr>))}</tbody>
                </table>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
