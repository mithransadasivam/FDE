// Routing: which fields go straight through, and which go to the KYC analysts (ticket ENG-602).
import { ArrowRight, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Comparison, type Routing, type RoutingSettings } from "../../api";
import { Card, Chip, Kpi, NotBuilt } from "../../components/ui";

const GRID = [0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99];

function Curve({ r }: { r: Routing }) {
  const W = 520, H = 230, L = 44, B = 34, T = 14, R = 14;
  const maxX = 50, maxY = Math.max(22, ...r.curve.map((p) => p.slipped));
  const x = (v: number) => L + (Math.min(v, maxX) / maxX) * (W - L - R);
  const y = (v: number) => T + (1 - v / maxY) * (H - T - B);
  const series = [false, true].map((a) => r.curve.filter((p) => p.agreement === a)).filter((s) => s.length);
  return (
    <svg width={W} height={H} data-testid="routing-curve" className="overflow-visible">
      {[0, 10, 20, 30, 40, 50].map((v) => <g key={v}><line x1={x(v)} x2={x(v)} y1={T} y2={H - B} stroke="#E6E8EF" /><text x={x(v)} y={H - B + 14} fontSize="10" textAnchor="middle" fill="#6B7090">{v}%</text></g>)}
      {[0, 5, 10, 15, 20].filter((v) => v <= maxY).map((v) => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="#E6E8EF" /><text x={L - 6} y={y(v) + 3} fontSize="10" textAnchor="end" fill="#6B7090">{v}</text></g>)}
      <text x={(L + W - R) / 2} y={H - 4} fontSize="10.5" textAnchor="middle" fill="#40456A">Fields sent to a person</text>
      <text x={12} y={(T + H - B) / 2} fontSize="10.5" textAnchor="middle" fill="#40456A" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>Errors that slip through</text>
      {series.map((s) => {
        const a = s[0].agreement, col = a ? "#0E8C7E" : "#E8552F";
        return (
          <g key={String(a)}>
            <polyline fill="none" stroke={col} strokeWidth="2" points={s.map((p) => `${x(p.review_pct)},${y(p.slipped)}`).join(" ")} />
            {s.map((p) => {
              const now = p.ok_at === r.ok_at && a === r.use_agreement;
              return <g key={p.ok_at}><circle cx={x(p.review_pct)} cy={y(p.slipped)} r={now ? 6 : 3.5} fill={now ? col : "#fff"} stroke={col} strokeWidth="2" />
                {(p.ok_at === 0.85 || p.ok_at === 0.99) && <text x={x(p.review_pct) + 7} y={y(p.slipped) - 7} fontSize="10" fill={col}>{p.ok_at}</text>}</g>;
            })}
            <text x={(x(s[3].review_pct) + x(s[s.length - 1].review_pct)) / 2} y={(y(s[3].slipped) + y(s[s.length - 1].slipped)) / 2 + (a ? 18 : -10)}
              fontSize="11" fontWeight="600" fill={col} textAnchor="middle">{a ? "confidence + agreement" : "confidence only"}</text>
          </g>
        );
      })}
    </svg>
  );
}

export default function RoutingTab({ set }: { set: string }) {
  const [cfg, setCfg] = useState<RoutingSettings | null>(null);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [r, setR] = useState<Routing | null>(null);
  const [nb, setNb] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.get<RoutingSettings>(`/api/pipeline/routing/settings?set=${set}`).then(setCfg);
    api.get<Comparison>(`/api/pipeline/compare?set=${set}`).then(setCmp);
  }, [set]);
  useEffect(() => {
    if (!cfg) return;
    setBusy(true); setNb("");
    api.post<Routing>("/api/pipeline/routing", { set, ...cfg }).then(setR)
      .catch((e) => { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; })
      .finally(() => setBusy(false));
  }, [cfg]);
  if (!cfg || !cmp) return null;
  const ran = new Set(cmp.runs.map((x) => x.prompt));
  const change = (patch: Partial<RoutingSettings>) => setCfg({ ...cfg, ...patch });
  const select = "rounded-lg border border-black/10 bg-white px-2 py-1.5 font-mono text-[12px]";
  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-end gap-4 px-4 py-3" testId="routing-controls">
        <label className="text-[11.5px] font-semibold text-ink-3">Fields read by
          <select data-testid="parser-prompt" className={`mt-1 block ${select}`} value={cfg.parser_prompt} onChange={(e) => change({ parser_prompt: e.target.value })}>
            {cmp.prompts.parser.map((p) => <option key={p} value={p} disabled={!ran.has(p)}>{p}{ran.has(p) ? "" : " (not run)"}</option>)}
          </select>
        </label>
        <label className="text-[11.5px] font-semibold text-ink-3">Checked against
          <select data-testid="vision-prompt" className={`mt-1 block ${select}`} value={cfg.vision_prompt} onChange={(e) => change({ vision_prompt: e.target.value })}>
            <option value="">nothing</option>
            {cmp.prompts.vision.map((p) => <option key={p} value={p} disabled={!ran.has(p)}>{p}{ran.has(p) ? "" : " (not run)"}</option>)}
          </select>
        </label>
        <label className="text-[11.5px] font-semibold text-ink-3">A person checks below confidence
          <select data-testid="ok-at" className={`mt-1 block ${select}`} value={cfg.ok_at} onChange={(e) => change({ ok_at: Number(e.target.value) })}>
            {GRID.map((g) => <option key={g} value={g}>{g.toFixed(2)}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-1.5 text-[12.5px] font-semibold">
          <input type="checkbox" data-testid="use-agreement" checked={cfg.use_agreement} onChange={(e) => change({ use_agreement: e.target.checked })} disabled={!cfg.vision_prompt} />
          Also check every field where the two methods disagree
        </label>
        {busy && <Loader2 size={15} className="mb-2 animate-spin text-ink-3" />}
        <a href="#/queue" data-testid="open-queue" className="mb-1.5 ml-auto inline-flex items-center gap-1 text-[12.5px] font-semibold text-teal">Open the Review queue <ArrowRight size={13} /></a>
      </Card>
      {nb && <NotBuilt ticket="ENG-602">{nb}. Open docs/tickets/ENG-602.md.</NotBuilt>}
      {r && !r.items && r.fields == null && <Card className="p-4 text-[12.5px] text-ink-2">Run {cfg.parser_prompt} on Pipeline → Compare first.</Card>}
      {r && r.fields != null && (
        <>
          <div className="grid grid-cols-4 gap-3" data-testid="routing-kpis">
            <Kpi label="Fields sent to a person" value={`${r.review_pct}%`} sub={`${r.review} of ${r.fields} fields`} tone="amber" />
            <Kpi label="Errors that slip through" value={r.slipped} tone={r.slipped > 5 ? "ember" : "teal"} sub={`Wrong, and accepted without a person (of ${r.errors} ${r.errors === 1 ? "error" : "errors"})`} />
            <Kpi label="Errors caught" value={r.caught} sub="Wrong, and sent to the Review queue" />
            <Kpi label="Right after the review" value={`${r.accuracy_after_review}%`} tone={r.accuracy_after_review >= r.human.one_keyer ? "teal" : "ember"}
              sub={`One keyer today: ${r.human.one_keyer}%`} />
          </div>
          <div className="grid grid-cols-[1.1fr_1fr] gap-4">
            <Card className="p-4" testId="routing-chart">
              <div className="text-[13.5px] font-semibold">Each threshold: how much work for people, and how many errors get through</div>
              <div className="mb-2 text-[12px] text-ink-2">Each point is one confidence threshold, from 0.60 to 0.99. Left and low is better. The big dot is the setting above.</div>
              <Curve r={r} />
            </Card>
            <div className="space-y-4">
              <Card className="p-4" testId="routing-reasons">
                <div className="text-[13.5px] font-semibold">Why fields go to a person</div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[12px]">
                  <div className="rounded-lg bg-mist p-2"><div className="text-[18px] font-semibold">{r.reasons.confidence}</div>low confidence</div>
                  <div className="rounded-lg bg-mist p-2"><div className="text-[18px] font-semibold">{r.reasons.not_on_page}</div>not on the page</div>
                  <div className="rounded-lg bg-mist p-2"><div className="text-[18px] font-semibold">{r.reasons.disagree}</div>methods disagree</div>
                </div>
              </Card>
              <Card className="overflow-hidden" testId="slipped">
                <div className="px-4 py-3 text-[13.5px] font-semibold">The {r.slipped} {r.slipped === 1 ? "error that gets" : "errors that get"} through</div>
                <div className="max-h-[210px] overflow-auto">
                  <table className="w-full text-left text-[12px]">
                    <thead className="sticky top-0 bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Doc</th><th>Field</th><th>Read</th><th>Answer</th><th className="pr-4 text-right">Conf.</th></tr></thead>
                    <tbody>
                      {r.slipped_items.map((s) => (
                        <tr key={`${s.doc_id}-${s.field}`} className="border-t border-black/[0.05]">
                          <td className="px-4 py-1.5 font-mono">{s.doc_id}</td><td>{s.label}</td><td className="font-semibold text-ember">{s.value}</td><td>{s.expected}</td>
                          <td className="pr-4 text-right tabular-nums">{s.confidence.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {r.slipped > 0 && <div className="border-t border-black/[0.05] px-4 py-2 text-[11.5px] text-ink-3">{r.use_agreement ? "Both methods read the same wrong value: agreement cannot catch these." : "High confidence, wrong value: the OCR read the words perfectly; the model chose the wrong ones."}</div>}
              </Card>
            </div>
          </div>
          <div className="flex gap-2 text-[11.5px] text-ink-3"><Chip>{r.parser_prompt}</Chip>{r.vision_prompt && <Chip>checked against {r.vision_prompt}</Chip>} The Review queue uses this setting.</div>
        </>
      )}
    </div>
  );
}
