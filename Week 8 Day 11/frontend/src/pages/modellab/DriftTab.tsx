// New document type (homework): council tax bills arrive. The cascade sends what the small model does not know to the
// pilot, which is safe but costs. retrain_candidates() (homework Task 1) says which kinds to retrain for.
import { Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type DriftResult } from "../../api";
import { Button, Card, Chip } from "../../components/ui";
import { FIELD_NAMES, KIND_NAMES, ModelPicker, pct, useDistil } from "./parts";

export default function DriftTab() {
  const { st } = useDistil();
  const [model, setModel] = useState<string | null>(null);
  const [d, setD] = useState<DriftResult | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (st && !model) setModel(st.active); }, [st]);
  const run = async () => {
    if (!model || !st) return;
    setBusy(true);
    try { setD(await api.get<DriftResult>(`/api/distil/drift?model=${model}&threshold=${st.threshold}`)); } finally { setBusy(false); }
  };
  useEffect(() => { if (model) run(); }, [model]);
  if (!st) return null;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><span className="text-[13px] text-ink-2">The October batch and the 20 council tax bills (Day 6 homework), at <b className="font-mono">{st.threshold.toFixed(2)}</b></span>
        <span className="ml-auto text-[12px] text-ink-3">Model</span><ModelPicker st={st} value={model} onChange={setModel} />
        <Button testId="run-drift" onClick={run} disabled={busy || !model}>{busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Check both sets</Button></div>
      {d && d.model && (
        <>
          <div className="grid grid-cols-2 gap-4">
            {(["october", "council_tax"] as const).map((k) => {
              const x = d[k];
              return (
                <Card key={k} className="p-4" testId={`drift-${k}`}>
                  <div className="text-[13.5px] font-semibold">{k === "october" ? "October batch: bills and statements" : "Council tax bills"} <span className="font-normal text-ink-3">· {x.documents} documents</span></div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-[12px]">
                    <div className="rounded-lg bg-mist px-3 py-2"><div className="text-ink-3">Small model alone</div><div className="text-[18px] font-semibold" data-testid={`alone-${k}`}>{pct(x.small_alone)}</div></div>
                    <div className="rounded-lg bg-mist px-3 py-2"><div className="text-ink-3">Sent to the pilot</div><div className="text-[18px] font-semibold" data-testid={`share-${k}`}>{Math.round(100 * x.teacher_share)}%</div></div>
                    <div className="rounded-lg bg-mist px-3 py-2"><div className="text-ink-3">Errors that slip through</div><div className="text-[18px] font-semibold">{x.slipped}</div></div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">{Object.entries(x.reasons).map(([r, n]) => <Chip key={r} tone="amber">{FIELD_NAMES[r.split(" ")[0]]} {r.split(" ")[1]} · {n}</Chip>)}</div>
                </Card>
              );
            })}
          </div>
          {!d.built ? (
            <div data-testid="not-built" className="rounded-xl border border-dashed border-amber bg-amber-50 p-5">
              <div className="text-[13px] font-semibold text-amber">Homework Task 1 is not built yet</div>
              <div className="mt-1 text-[12.5px] leading-relaxed text-ink-2">Fill in <code>retrain_candidates()</code> in <code>backend/app/distil/drift.py</code>: for each kind of document, the share that goes to the pilot, the field named most often, and whether to retrain.</div>
            </div>
          ) : (
            <Card className="overflow-hidden" testId="candidates">
              <div className="px-4 py-2 text-[13px] font-semibold">Which kinds to retrain for</div>
              <table className="w-full text-[12.5px]">
                <thead className="bg-mist text-left text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Kind</th><th className="text-right">Documents</th><th className="text-right">To the pilot</th><th className="text-right">Share</th><th className="px-4">Field named most</th><th className="px-4">Retrain?</th></tr></thead>
                <tbody>{d.candidates.map((c) => (
                  <tr key={c.kind} data-testid={`cand-${c.kind}`} className="border-t border-black/[0.05]"><td className="px-4 py-1.5">{KIND_NAMES[c.kind] ?? c.kind}</td>
                    <td className="text-right">{c.documents}</td><td className="text-right">{c.to_teacher}</td><td className="text-right font-semibold">{Math.round(100 * c.share)}%</td>
                    <td className="px-4">{c.top_reason ? FIELD_NAMES[c.top_reason] : "–"}</td>
                    <td className="px-4"><Chip tone={c.retrain ? "ember" : "teal"}>{c.retrain ? "retrain" : "no"}</Chip></td></tr>))}</tbody>
              </table>
            </Card>
          )}
          <div className="text-[12px] text-ink-2">To retrain: <b>Teacher and student</b>, tick <b>council_tax</b> as well as pilot, and press Train. Then check both sets again: October must not get worse.</div>
        </>
      )}
    </div>
  );
}
