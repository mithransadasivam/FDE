// Error analysis: run the prototype on the 50 checked documents, read every wrong field, tag it, and count the tags.
import { Loader2, Play, Tags } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type EvalRun, type TaxonomyRow } from "../../api";
import { Button, Card, Chip, Kpi, NotBuilt } from "../../components/ui";
import { Pareto } from "../../components/evalViz";

const LABEL: Record<string, string> = { full_name: "Full name", address: "Address", statement_date: "Statement date", issuer: "Issuer", decision: "Decision" };

export default function ErrorsTab() {
  const [run, setRun] = useState<EvalRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [nb, setNb] = useState("");
  const [tags, setTags] = useState<Record<string, string>>({});
  const [tax, setTax] = useState<TaxonomyRow[]>([]);
  const [tom, setTom] = useState<TaxonomyRow[] | null>(null);
  useEffect(() => {
    api.get<EvalRun>("/api/eval/runs/extract__real").then(setRun).catch(() => {});
    api.get<{ tags: Record<string, string>; taxonomy: TaxonomyRow[] }>("/api/eval/tags").then((r) => { setTags(r.tags); setTax(r.taxonomy); });
  }, []);
  const go = async () => {
    setBusy(true); setNb("");
    try { setRun(await api.post<EvalRun>("/api/eval/runs", { prompt: "extract", set: "real" })); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; }
    finally { setBusy(false); }
  };
  const tag = async (key: string, type: string) => {
    const r = await api.put<{ tags: Record<string, string>; taxonomy: TaxonomyRow[] }>("/api/eval/tags", { key, type });
    setTags(r.tags); setTax(r.taxonomy);
  };
  const types = Array.from(new Set(Object.values(tags).filter(Boolean)));
  const s = run?.score;
  const rows = s && run ? [...s.errors, ...run.rules.errors] : [];
  return (
    <div>
      <Card className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="text-[14px] font-semibold">The evaluation set: 50 documents Tom checked</div>
          <div className="text-[12.5px] text-ink-2">Day 3's 30, and 20 harder ones from last month · data/Day04_Slide10_eval_labels.csv · prompt: extract (Day 3)</div>
        </div>
        <Button onClick={go} disabled={busy} testId="run-eval">{busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} {run ? "Run again" : "Run the prototype on all 50"}</Button>
      </Card>
      {nb && <div className="mt-3"><NotBuilt ticket="ENG-402">{nb}. Open docs/tickets/ENG-402.md.</NotBuilt></div>}
      {s && (
        <>
          <div className="mt-4 grid grid-cols-5 gap-3" data-testid="eval-kpis">
            <Kpi label="Fields right" value={<span data-testid="accuracy">{s.overall.accuracy}%</span>} tone="teal" sub={`${s.overall.correct} of ${s.overall.total}`} />
            {Object.entries(s.per_field).map(([f, v]) => (
              <Kpi key={f} label={LABEL[f]} value={`${v.accuracy}%`} tone={v.accuracy < 95 ? "amber" : "ink"} sub={`${v.total - v.correct} wrong`} />
            ))}
          </div>
          <div className="mt-4 grid grid-cols-[minmax(0,1fr)_540px] gap-4">
            <Card className="overflow-hidden" testId="errors">
              <div className="flex items-center justify-between px-4 pt-3">
                <div className="text-[13px] font-semibold">{s.errors.length} wrong fields and {run!.rules.errors.length} wrong decisions: read each one, then name what went wrong</div>
                <span className="text-[11.5px] text-ink-3">{Object.keys(tags).length} of {rows.length} tagged</span>
              </div>
              <datalist id="types">{types.map((t) => <option key={t} value={t} />)}</datalist>
              <table className="mt-2 w-full text-[12.5px]">
                <thead className="bg-mist text-left text-[11px] uppercase tracking-wide text-ink-3">
                  <tr><th className="w-[84px] px-4 py-2">Case</th><th className="w-[110px]">Field</th><th>The prototype read</th><th>Tom says</th><th className="w-[190px] pr-4">Failure type</th></tr>
                </thead>
                <tbody>
                  {rows.map((e) => {
                    const key = `${e.case_id}|${e.field}`;
                    return (
                      <tr key={key} data-testid={`err-${key}`} className="border-t border-black/[0.05] align-top">
                        <td className="whitespace-nowrap px-4 py-2 font-mono text-[11.5px] text-ink-2">{e.case_id}</td>
                        <td className="py-2">{LABEL[e.field]}</td>
                        <td className="py-2 font-semibold text-ember">{e.got || "—"}</td>
                        <td className="py-2 font-semibold text-teal">{e.expected}</td>
                        <td className="py-1.5 pr-4">
                          <input list="types" defaultValue={tags[key] ?? ""} placeholder="e.g. wrong date chosen" data-testid={`tag-${key}`}
                            onBlur={(ev) => ev.target.value !== (tags[key] ?? "") && tag(key, ev.target.value)}
                            className="w-full rounded-md border border-black/10 px-2 py-1 text-[12px] outline-none focus:border-navy" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
            <Card className="p-4" testId="taxonomy">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[13px] font-semibold"><Tags size={15} /> {tom ? "Tom's failure tags" : "Your failure taxonomy"}</div>
                <Button variant="secondary" testId="toggle-tom" onClick={async () => setTom(tom ? null : (await api.get<{ taxonomy: TaxonomyRow[] }>("/api/eval/tom-tags")).taxonomy)}>
                  {tom ? "Show mine" : "Compare with Tom's"}
                </Button>
              </div>
              {(tom ?? tax).length === 0 ? (
                <div className="mt-6 text-[12.5px] text-ink-2">Tag the wrong fields on the left. Use the same name for the same problem: the chart counts them.</div>
              ) : (
                <>
                  <Pareto rows={tom ?? tax} testId="pareto" />
                  <div className="mt-1 text-[12px] text-ink-2">Bars: how often each failure happens. Line: the running share. The two dark bars are where to look first.</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">{(tom ?? tax).map((r) => <Chip key={r.type}>{r.type} · {r.count}</Chip>)}</div>
                </>
              )}
              {run && <div className="mt-3 rounded-lg bg-mist px-3 py-2 text-[12px] text-ink-2">Rules agree with Tom's decision on {run.rules.agree} of {run.rules.compared} cases: a wrong decision with right fields is a failure too.</div>}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
