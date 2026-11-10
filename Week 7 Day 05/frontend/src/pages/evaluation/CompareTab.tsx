// Before and after: compare two runs slice by slice, on real and synthetic cases.
import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type EvalRun, type RunSummary } from "../../api";
import { Card, Chip } from "../../components/ui";

function pick(runs: RunSummary[]): [string, string] | null {
  const by = (n: string) => runs.find((r) => r.name === n)?.name;
  const before = by("extract__all") ?? by("extract__real");
  const after = by("extract_v2__all") ?? by("extract_v2__real");
  if (before && after) return [before, after];
  if (runs.length >= 2) return [runs[0].name, runs[runs.length - 1].name];
  return null;
}

export default function CompareTab() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [names, setNames] = useState<[string, string] | null>(null);
  const [pair, setPair] = useState<[EvalRun, EvalRun] | null>(null);
  useEffect(() => { api.get<RunSummary[]>("/api/eval/runs").then((r) => { setRuns(r); setNames(pick(r)); }); }, []);
  useEffect(() => {
    if (!names) return;
    Promise.all(names.map((n) => api.get<EvalRun>(`/api/eval/runs/${n}`))).then((p) => setPair([p[0], p[1]]));
  }, [names]);
  if (!runs.length || !names) return (
    <Card className="p-5" testId="no-runs">
      <div className="text-[14px] font-semibold">Two runs are needed</div>
      <div className="mt-1 text-[13px] text-ink-2">From backend/, run the Day 3 prompt and your fixed prompt over the same set:</div>
      <pre className="mt-2 rounded-lg bg-navy px-3 py-2 text-[12.5px] text-white">python -m scripts.run_eval --set all{"\n"}python -m scripts.run_eval --prompt extract_v2 --set all</pre>
    </Card>
  );
  const sel = (i: 0 | 1) => (
    <select data-testid={`run-${i ? "after" : "before"}`} value={names[i]} onChange={(e) => setNames(i ? [names[0], e.target.value] : [e.target.value, names[1]])}
      className="rounded-lg border border-black/10 bg-white px-2 py-1.5 font-mono text-[12px]">
      {runs.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
    </select>
  );
  if (!pair) return null;
  const [b, a] = pair;
  const slices = Array.from(new Set([...Object.keys(b.score.per_slice), ...Object.keys(a.score.per_slice)])).filter((s) => s !== "synthetic");
  const delta = Math.round((a.score.overall.accuracy - b.score.overall.accuracy) * 10) / 10;
  return (
    <div>
      <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="text-[13px] font-semibold">Before</span>{sel(0)}<ArrowRight size={15} className="text-ink-3" /><span className="text-[13px] font-semibold">After</span>{sel(1)}
        <span className="ml-auto text-[12px] text-ink-2">{a.cases} cases · {Object.keys(a.score.per_slice).includes("synthetic") ? `${a.score.per_slice.synthetic.total / 4} synthetic` : "no synthetic"}</span>
      </Card>
      <div className="mt-4 grid grid-cols-[300px_minmax(0,1fr)] gap-4">
        <Card className="p-4" testId="overall">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">Fields right, all cases</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-[22px] font-semibold text-ink-3">{b.score.overall.accuracy}%</span>
            <ArrowRight size={16} className="text-ink-3" />
            <span data-testid="after-accuracy" className="text-[30px] font-semibold text-teal">{a.score.overall.accuracy}%</span>
          </div>
          <Chip tone={delta >= 0 ? "teal" : "ember"}>{delta >= 0 ? "+" : ""}{delta} points</Chip>
          <div className="mt-4 text-[12px] text-ink-2">Wrong fields: {b.score.errors.length} → <b>{a.score.errors.length}</b></div>
          <div className="mt-1 text-[12px] text-ink-2">Rules agree with Tom: {b.rules.agree}/{b.rules.compared} → {a.rules.agree}/{a.rules.compared}</div>
          <div className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-[12px] text-ink-2">A fix that helps one slice can hurt another. Read every row on the right, not only the total.</div>
        </Card>
        <Card className="p-4" testId="slices">
          <div className="text-[13px] font-semibold">By slice: before (grey) and after (teal)</div>
          <div className="mt-3 space-y-2.5">
            {slices.map((s) => {
              const x = b.score.per_slice[s], y = a.score.per_slice[s];
              const changed = x && y && x.accuracy !== y.accuracy;
              return (
                <div key={s} data-testid={`slice-${s}`} className="grid grid-cols-[150px_1fr_110px] items-center gap-3 text-[12.5px]">
                  <span className={changed ? "font-semibold" : "text-ink-2"}>{s.replace(/_/g, " ")}</span>
                  <div className="space-y-1">
                    <div className="h-2.5 rounded-full bg-mist"><div className="h-2.5 rounded-full bg-[#B7BCD0]" style={{ width: `${x?.accuracy ?? 0}%` }} /></div>
                    <div className="h-2.5 rounded-full bg-mist"><div className={`h-2.5 rounded-full ${y && x && y.accuracy < x.accuracy ? "bg-ember" : "bg-teal"}`} style={{ width: `${y?.accuracy ?? 0}%` }} /></div>
                  </div>
                  <span className="text-right tabular-nums">{x?.accuracy ?? "—"}% → <b>{y?.accuracy ?? "—"}%</b></span>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );
}
