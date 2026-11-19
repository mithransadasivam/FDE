// Batch: the whole pipeline on all 200 documents, as it would run every night. Throughput, failures, cost, people.
import { Loader2, Play, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type BatchReport, type RoutingSettings } from "../../api";
import { Button, Card, Chip, Kpi, NotBuilt } from "../../components/ui";

const LEVELS = [1, 4, 8, 12, 16, 32];
const mins = (ms: number) => (ms >= 60000 ? `${(ms / 60000).toFixed(1)} min` : `${Math.round(ms / 1000)} s`);

export default function BatchTab({ set }: { set: string }) {
  const [rep, setRep] = useState<BatchReport | null>(null);
  const [cfg, setCfg] = useState<RoutingSettings | null>(null);
  const [conc, setConc] = useState(8);
  const [busy, setBusy] = useState("");
  const [nb, setNb] = useState("");
  useEffect(() => {
    api.get<BatchReport>(`/api/pipeline/batch?set=${set}`).then((r) => setRep(r && r.run ? r : null));
    api.get<RoutingSettings>(`/api/pipeline/routing/settings?set=${set}`).then(setCfg);
  }, [set]);
  if (!cfg) return null;
  const go = async (resume: boolean) => {
    setBusy(resume ? "resume" : "run"); setNb("");
    try { setRep(await api.post<BatchReport>("/api/pipeline/batch", { set, ...cfg, concurrency: conc, resume })); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; }
    finally { setBusy(""); }
  };
  const failed = rep?.run.failed_docs.length ?? 0;
  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-4 px-4 py-3" testId="batch-controls">
        <div>
          <div className="text-[13.5px] font-semibold">Run the whole pipeline on the 200</div>
          <div className="text-[12px] text-ink-2">Parse, read with <span className="font-mono">{cfg.parser_prompt}</span>{cfg.vision_prompt && <> and <span className="font-mono">{cfg.vision_prompt}</span></>}, route with the setting from Routing. Two model calls per document.</div>
        </div>
        <div className="ml-auto flex items-center gap-1.5 text-[12px] font-semibold text-ink-3">Calls at once
          {LEVELS.map((n) => (
            <button key={n} data-testid={`conc-${n}`} onClick={() => setConc(n)}
              className={`h-7 w-9 rounded-md text-[12px] font-semibold ${conc === n ? "bg-navy text-white" : "bg-mist text-ink-2"}`}>{n}</button>
          ))}
        </div>
        <Button onClick={() => go(false)} disabled={!!busy} testId="run-batch">{busy === "run" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run the batch</Button>
        {failed > 0 && <Button variant="secondary" onClick={() => go(true)} disabled={!!busy} testId="resume-batch">
          {busy === "resume" ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />} Run the {failed} unfinished again</Button>}
      </Card>
      {nb && <NotBuilt ticket="ENG-601 or ENG-602">{nb}. The batch needs both tickets: docs/tickets/ENG-601.md and ENG-602.md.</NotBuilt>}
      {rep && (
        <div data-testid="batch-report" className="space-y-4">
          <div className="grid grid-cols-5 gap-3">
            <Kpi label="Documents finished" value={`${rep.run.complete} of ${rep.run.documents}`} tone={rep.run.complete < rep.run.documents ? "ember" : "teal"}
              sub={rep.run.complete < rep.run.documents ? `${failed} need running again` : rep.run.resume ? `${rep.run.finished_now} finished on this run` : `${rep.run.calls} calls, ${rep.concurrency} at once`} />
            <Kpi label="Refused: too many requests" value={rep.run.refusals} tone={rep.run.refusals ? "ember" : "ink"} sub="HTTP 429s, retried with a growing wait" />
            <Kpi label={rep.run.simulated ? "Time (simulated)" : "Time"} value={mins(rep.run.wall_ms)} sub={`p50 ${(rep.run.latency_ms_p50 / 1000).toFixed(1)} s · p95 ${(rep.run.latency_ms_p95 / 1000).toFixed(1)} s per call`} />
            <Kpi label="Throughput" value={`${rep.throughput_docs_per_min} / min`} sub="Documents finished per minute" />
            <Kpi label="A month of documents" value={rep.month_minutes != null ? mins(rep.month_minutes * 60000) : "—"}
              sub={rep.month_minutes != null ? `${rep.docs_per_month.toLocaleString()} documents at this rate` : "Run all 200 to measure"} />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <Card className="p-4" testId="batch-accuracy">
              <div className="text-[13.5px] font-semibold">Accuracy</div>
              <table className="mt-2 w-full text-[12.5px]"><tbody>
                {[["Parser + LLM alone", rep.accuracy.parser], ["Vision model alone", rep.accuracy.vision], ["One keyer at the bank today", rep.accuracy.one_keyer]].map(([k, v]) => (
                  <tr key={k as string} className="border-t border-black/[0.05]"><td className="py-1.5 text-ink-2">{k}</td><td className="text-right tabular-nums">{v != null ? `${v}%` : "—"}</td></tr>))}
                <tr className="border-t border-black/[0.05]"><td className="py-1.5 font-semibold">The pipeline, after the Review queue</td>
                  <td className={`text-right font-semibold tabular-nums ${rep.accuracy.after_review >= rep.accuracy.one_keyer ? "text-teal" : "text-ember"}`}>{rep.accuracy.after_review}%</td></tr>
              </tbody></table>
              <div className="mt-2 text-[11.5px] text-ink-3">{rep.routing.review} fields ({rep.routing.review_pct}%) to the Review queue · {rep.routing.slipped} errors not caught. Assumes the team corrects what it is shown.</div>
            </Card>
            <Card className="p-4" testId="batch-cost">
              <div className="text-[13.5px] font-semibold">Model cost</div>
              <div className="text-[11.5px] text-ink-3">{rep.tokens_per_doc.input.toLocaleString()} input and {rep.tokens_per_doc.output} output tokens per document, both methods.</div>
              <table className="mt-2 w-full text-[12.5px]"><tbody>
                {[["Class model", rep.cost.class], ["Pilot: Sonnet 5 in London", rep.cost.pilot], ["Pilot, as a batch job", rep.cost.pilot_batch]].map(([k, c]) => {
                  const cc = c as BatchReport["cost"]["class"];
                  return <tr key={k as string} className="border-t border-black/[0.05]"><td className="py-1.5"><div className="font-semibold">{k as string}</div><div className="font-mono text-[10.5px] text-ink-3">{cc.model}</div></td>
                    <td className="text-right tabular-nums">USD {cc.usd_per_doc?.toFixed(5) ?? "—"}<div className="text-[11px] text-ink-3">£{cc.gbp_per_month ?? "—"} a month</div></td></tr>;
                })}
              </tbody></table>
              <div className="mt-2 text-[11.5px] text-ink-3">{rep.cost.pilot_batch.note}.</div>
            </Card>
            <Card className="p-4" testId="batch-people">
              <div className="text-[13.5px] font-semibold">Fields a person handles, a month</div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-center">
                <div className="rounded-lg bg-mist p-3"><div className="text-[24px] font-semibold">{rep.fields_per_month.typed_today.toLocaleString()}</div><div className="text-[11.5px] text-ink-2">today: every field copy-typed into CaseFlow</div></div>
                <div className="rounded-lg bg-teal-50 p-3"><div className="text-[24px] font-semibold text-teal">{rep.fields_per_month.checked_with_pipeline.toLocaleString()}</div><div className="text-[11.5px] text-ink-2">with the pipeline: checked in the Review queue ({rep.routing.review_pct}%)</div></div>
              </div>
              <div className="mt-2 text-[11.5px] text-ink-3">4 fields on each of {rep.docs_per_month.toLocaleString()} documents. The decision on each application stays with the analysts.</div>
            </Card>
          </div>
          {rep.history?.length > 0 && (
            <Card className="overflow-hidden" testId="batch-history">
              <div className="px-4 py-3 text-[13.5px] font-semibold">Runs so far</div>
              <table className="w-full text-left text-[12.5px]">
                <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Calls at once</th><th>Run</th><th className="text-right">Calls</th><th className="text-right">Finished</th><th className="text-right">Unfinished</th><th className="text-right">Refused (429)</th><th className="text-right">Time</th><th className="pr-4 text-right">Docs / min</th></tr></thead>
                <tbody>
                  {rep.history.map((h, i) => (
                    <tr key={i} className="border-t border-black/[0.05]">
                      <td className="px-4 py-1.5 font-semibold">{h.concurrency}</td><td>{h.resume ? <Chip>again, unfinished only</Chip> : "all 200"}</td>
                      <td className="text-right tabular-nums">{h.calls}</td><td className="text-right tabular-nums">{h.complete}</td>
                      <td className={`text-right tabular-nums ${h.failed_docs ? "font-semibold text-ember" : ""}`}>{h.failed_docs}</td>
                      <td className={`text-right tabular-nums ${h.refusals ? "text-ember" : ""}`}>{h.refusals}</td>
                      <td className="text-right tabular-nums">{mins(h.wall_ms)}{h.simulated ? "*" : ""}</td><td className="pr-4 text-right tabular-nums">{h.docs_per_min}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="border-t border-black/[0.05] px-4 py-2 text-[11.5px] text-ink-3">* simulated time: on the scripted model, the account accepts 8 calls at once, like a real rate limit.</div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
