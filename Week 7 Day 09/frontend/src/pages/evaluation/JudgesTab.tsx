// LLM judges: one per frequent failure type, calibrated against Tom's tags before anyone trusts them.
import { Bot, Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type JudgeInfo, type JudgeResult } from "../../api";
import { Button, Card, Chip, NotBuilt } from "../../components/ui";
import { Matrix } from "../../components/evalViz";

const NAMES: Record<string, string> = { wrong_date: "Wrong date chosen", incomplete_name: "Incomplete name" };

function JudgeCard({ j, results, onRun }: { j: JudgeInfo; results: Record<string, JudgeResult>; onRun: (stem: string) => Promise<void> }) {
  const [stem, setStem] = useState(j.prompts[j.prompts.length - 1] ?? j.judge);
  const [busy, setBusy] = useState(false);
  const r = results[stem];
  const a = r?.agreement;
  const run = async () => { setBusy(true); try { await onRun(stem); } finally { setBusy(false); } };
  const metric = (label: string, v: number | null, good: boolean, testId: string, sub: string) => (
    <div className="rounded-lg bg-mist px-3 py-2">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">{label}</div>
      <div data-testid={testId} className={`text-[22px] font-semibold leading-tight ${v === null ? "text-ink-3" : good ? "text-teal" : "text-amber"}`}>{v ?? "—"}</div>
      <div className="text-[11px] text-ink-2">{sub}</div>
    </div>
  );
  return (
    <Card className="p-4" testId={`judge-${j.judge}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-navy"><Bot size={17} className="text-white" /></div>
          <div>
            <div className="text-[14px] font-semibold">{NAMES[j.judge] ?? j.judge}</div>
            <div className="text-[11.5px] text-ink-3">reads {j.field} · calibrated against Tom's “{j.failure_type}” tags</div>
          </div>
        </div>
        <div className="shrink-0"><Button onClick={run} disabled={busy} testId={`run-${j.judge}`}>{busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run judge</Button></div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {j.prompts.map((p) => (
          <button key={p} data-testid={`prompt-${p}`} onClick={() => setStem(p)}
            className={`rounded-full border px-2.5 py-0.5 font-mono text-[11.5px] ${p === stem ? "border-navy bg-navy text-white" : "border-black/10 text-ink-2"}`}>evals/judges/{p}.md</button>
        ))}
      </div>
      {a ? (
        <>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {metric("Caught", a.caught, (a.caught ?? 0) >= 0.9, `caught-${j.judge}`, `${a.tp} of ${a.tp + a.fn} of Tom's failures`)}
            {metric("Cleared", a.cleared, (a.cleared ?? 0) >= 0.95, `cleared-${j.judge}`, `${a.tn} of ${a.tn + a.fp} good values`)}
            {metric("Kappa", a.kappa, a.kappa >= 0.8, `kappa-${j.judge}`, `${a.percent}% agreement`)}
          </div>
          <div className="mt-3"><Matrix a={a} rater="Judge" expert="Tom" pos="fail" neg="pass" /></div>
          <div className="mt-3 text-[12px] font-semibold">{a.disagreements.length ? "Where the judge and Tom disagree" : "The judge agrees with Tom on every case"}</div>
          {a.disagreements.map((cid) => {
            const v = r.verdicts[cid];
            return (
              <div key={cid} data-testid="judge-disagreement" className="mt-1.5 rounded-lg border border-ember/30 bg-ember-50 px-3 py-2 text-[12px]">
                <div><span className="font-mono text-ink-3">{cid}</span> <Chip tone={v.verdict === "fail" ? "ember" : "teal"}>judge: {v.verdict}</Chip> <Chip tone={v.expert === "fail" ? "ember" : "teal"}>Tom: {v.expert}</Chip> value <b>{v.value}</b></div>
                <div className="mt-0.5 text-ink-2">“{v.reason}”</div>
              </div>
            );
          })}
        </>
      ) : <div className="mt-4 text-[12.5px] text-ink-2">Not run yet with this prompt.</div>}
    </Card>
  );
}

export default function JudgesTab() {
  const [d, setD] = useState<{ judges: JudgeInfo[]; results: Record<string, JudgeResult> } | null>(null);
  const [nb, setNb] = useState("");
  const load = () => api.get<{ judges: JudgeInfo[]; results: Record<string, JudgeResult> }>("/api/eval/judges").then(setD);
  useEffect(() => { load(); }, []);
  const run = async (stem: string) => {
    setNb("");
    try { await api.post(`/api/eval/judges/${stem}/run`); await load(); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; }
  };
  if (!d) return null;
  return (
    <div>
      <Card className="px-4 py-3">
        <div className="text-[14px] font-semibold">A judge is a model that checks one thing. Trust it only after it agrees with the expert.</div>
        <div className="text-[12.5px] text-ink-2">Each judge runs on the Day 3 prompt's outputs for the 50 real cases. Aim for caught ≥ 0.9, cleared ≥ 0.95 and kappa ≥ 0.8 before you use it on new data.</div>
      </Card>
      {nb && <div className="mt-3"><NotBuilt ticket="ENG-401">{nb}. Open docs/tickets/ENG-401.md.</NotBuilt></div>}
      <div className="mt-4 grid grid-cols-2 gap-4">
        {d.judges.map((j) => <JudgeCard key={j.judge} j={j} results={d.results} onRun={run} />)}
      </div>
    </div>
  );
}
