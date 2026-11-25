// Evaluation: the bank's business questions, each asked as the person who asked it, scored against the bank's own answers.
import { CheckCircle2, FlaskConical, Loader2, Play, RefreshCw, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type AgentEvalRun, type EvalView } from "../../api";
import { Button, Card, Chip, NotBuilt } from "../../components/ui";
import { ResultTable, Sql, brief } from "./shared";

const BAR = 90; // Deborah: nine in ten of her questions answered right
const SET_KEY = "fde.data.set";
const WHO: Record<string, string> = { "helen.achebe": "Helen", "grace.mensah": "Grace", "tom.reyes": "Tom" };

export default function EvalTab() {
  const [set, setSet] = useState(() => { try { return localStorage.getItem(SET_KEY) || "bank30"; } catch { return "bank30"; } });
  const [v, setV] = useState<EvalView | null>(null);
  const [layer, setLayer] = useState("");
  const [run, setRun] = useState<AgentEvalRun | null>(null);
  const [busy, setBusy] = useState("");
  const [nb, setNb] = useState("");
  const [sel, setSel] = useState("");
  const [only, setOnly] = useState(false);
  const load = () => api.get<EvalView>(`/api/data/eval?set=${set}`).then((x) => {
    setV(x);
    if (!x.sets[set]) setSet("bank30");
    setLayer((l) => (l && x.runs.some((r) => r.layer === l) ? l : x.runs[x.runs.length - 1]?.layer ?? ""));
  });
  useEffect(() => { try { localStorage.setItem(SET_KEY, set); } catch { /* private window */ } setRun(null); setLayer(""); load(); }, [set]);
  useEffect(() => { if (layer) api.get<AgentEvalRun>(`/api/data/eval/results?set=${set}&layer=${layer}`).then(setRun).catch(() => setRun(null)); }, [layer, v]);
  if (!v) return null;
  const go = async (l: string) => {
    setBusy(l); setNb("");
    try { await api.post("/api/data/eval/run", { set, layer: l }); setLayer(l); await load(); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; }
    finally { setBusy(""); }
  };
  const byLayer = Object.fromEntries(v.runs.map((r) => [r.layer, r]));
  const cur = byLayer[layer];
  const results = (run?.results ?? []).filter((r) => !only || !r.right);
  const detail = run?.results.find((r) => r.id === sel);
  const top = cur?.failures[0];
  const wrong = cur ? cur.questions - cur.right : 0;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[1fr_1.5fr] gap-4">
        <Card className="p-4" testId="eval-controls">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-[13.5px] font-semibold"><FlaskConical size={15} /> Ask every question</div>
            <select data-testid="eval-set" value={set} onChange={(e) => setSet(e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1.5 text-[12px]">
              {Object.entries(v.sets).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
            </select>
          </div>
          <div className="mt-0.5 text-[12px] text-ink-2">Each question is asked as the person who asked it, so row security is part of the test. Right means the same values as the bank's own query.</div>
          <div className="mt-3 space-y-1.5">
            {v.layers.map((l) => (
              <div key={l} className="flex items-center justify-between rounded-lg border border-black/[0.06] px-3 py-2">
                <div className="flex items-center gap-2 text-[12.5px]"><span className="font-mono font-semibold">{l}</span>
                  {byLayer[l] && <Chip tone={byLayer[l].pct >= BAR ? "teal" : "ember"}>{byLayer[l].right} of {byLayer[l].questions}</Chip>}</div>
                <Button variant="secondary" onClick={() => go(l)} disabled={!!busy} testId={`run-${l}`}>
                  {busy === l ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} {byLayer[l] ? "Run again" : "Run"}
                </Button>
              </div>
            ))}
          </div>
          <div className="mt-2 text-[11.5px] text-ink-3">Deborah's bar: {BAR}% right, and nothing unsafe ever runs.</div>
        </Card>

        <Card className="overflow-hidden" testId="eval-runs">
          <div className="px-4 py-3 text-[13.5px] font-semibold">Runs on {v.sets[set]?.label.toLowerCase()}</div>
          <table className="w-full text-left text-[12.5px]">
            <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
              <tr><th className="px-4 py-1.5">Semantic layer</th><th className="text-right">Right</th><th className="text-right">Repaired</th><th className="text-right">Refused</th>
                <th className="pl-4">Failures</th><th className="text-right">Tokens in</th><th className="pr-4 text-right">£ a month, pilot</th></tr>
            </thead>
            <tbody>
              {v.runs.length === 0 && <tr><td colSpan={7} className="px-4 py-4 text-ink-3">No runs yet.</td></tr>}
              {v.runs.map((r) => (
                <tr key={r.layer} data-testid={`evrun-${r.layer}`} onClick={() => setLayer(r.layer)} className={`cursor-pointer border-t border-black/[0.05] ${layer === r.layer ? "bg-amber-50/60" : ""}`}>
                  <td className="px-4 py-2 font-mono text-[12px] font-semibold">{r.layer}</td>
                  <td className={`text-right font-semibold ${r.pct >= BAR ? "text-teal" : "text-ember"}`}>{r.right} / {r.questions} · {r.pct.toFixed(1)}%</td>
                  <td className="text-right tabular-nums">{r.repaired}</td>
                  <td className="text-right tabular-nums">{r.refused}</td>
                  <td className="pl-4 text-[11.5px] text-ink-2">{r.failures.map((f) => `${f.kind} ${f.count}`).join(" · ") || "none"}</td>
                  <td className="text-right tabular-nums">{r.tokens_in.toLocaleString()}</td>
                  <td className="pr-4 text-right tabular-nums">{r.cost.pilot ? `£${r.cost.pilot.gbp_per_month.toFixed(2)}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {cur && <div className="border-t border-black/[0.05] px-4 py-2 text-[11.5px] text-ink-3">
            Cost: {v.questions_per_month.toLocaleString()} questions a month (an assumption) on Claude Sonnet 5 in London; on {cur.cost.class?.model ?? "the class model"} £{cur.cost.class?.gbp_per_month.toFixed(2)}.
          </div>}
        </Card>
      </div>
      {nb && <NotBuilt ticket={nb.includes("ENG-702") ? "ENG-702" : "ENG-701"}>{nb}. The evaluation runs every query through both checks.</NotBuilt>}

      {cur && top && (
        <Card className="flex items-center gap-4 border-amber/40 bg-amber-50/50 px-4 py-3" testId="top-failure">
          <div className="text-[13px]"><span className="font-semibold">Most common failure with {cur.layer}: {top.kind}</span>, {top.count} of the {wrong} wrong answers.</div>
          <div className="ml-auto flex gap-1.5">{cur.failures.map((f) => <Chip key={f.kind} tone={f === top ? "amber" : "mist"}>{f.kind}: {f.count}</Chip>)}</div>
        </Card>
      )}

      {run && (
        <div className="grid grid-cols-[1.4fr_1fr] gap-4">
          <Card className="overflow-hidden" testId="eval-results">
            <div className="flex items-center justify-between px-4 py-3">
              <div className="text-[13.5px] font-semibold">Question by question: <span className="font-mono">{run.layer}</span></div>
              <label className="flex items-center gap-1.5 text-[12px] text-ink-2"><input type="checkbox" checked={only} onChange={(e) => setOnly(e.target.checked)} data-testid="only-wrong" /> Wrong only</label>
            </div>
            <table className="w-full text-left text-[12px]">
              <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
                <tr><th className="px-4 py-1.5">#</th><th>Asked by</th><th>Question</th><th>The bank's answer</th><th>The agent's</th><th className="pr-4">Result</th></tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.id} data-testid={`evq-${r.id}`} onClick={() => setSel(r.id)} className={`cursor-pointer border-t border-black/[0.05] align-top ${sel === r.id ? "bg-amber-50/60" : ""}`}>
                    <td className="px-4 py-1.5 text-ink-3">{r.id}</td>
                    <td className="py-1.5 pr-2">{WHO[r.user] ?? r.user}</td>
                    <td className="max-w-[300px] py-1.5 pr-2">{r.question}</td>
                    <td className="max-w-[150px] py-1.5 pr-2 tabular-nums text-ink-2 [overflow-wrap:anywhere]">{r.expected.rows.length ? brief(r.expected.rows, 2) : "cannot answer"}</td>
                    <td className="max-w-[150px] py-1.5 pr-2 tabular-nums text-ink-2 [overflow-wrap:anywhere]">{r.answer.status === "answered" ? brief(r.answer.rows, 2) : r.answer.status.replace("_", " ")}</td>
                    <td className="py-1.5 pr-4">
                      {r.right ? <Chip tone="teal"><CheckCircle2 size={11} /> right</Chip> : <Chip tone="ember"><XCircle size={11} /> {r.failure}</Chip>}
                      {r.repaired && <span className="ml-1"><Chip tone="mist"><RefreshCw size={10} /> repaired</Chip></span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card className="sticky top-0 self-start p-4" testId="eval-detail">
            {!detail ? <div className="text-[12.5px] text-ink-3">Click a question to see the agent's query, what it assumed, and the bank's answer.</div> : (
              <div className="space-y-3">
                <div className="text-[13.5px] font-semibold">{detail.id} · {detail.question}</div>
                <div className="flex flex-wrap gap-1.5">{detail.tags.map((t) => <Chip key={t}>{t}</Chip>)}{detail.right ? <Chip tone="teal">right</Chip> : <Chip tone="ember">{detail.failure}</Chip>}</div>
                {detail.answer.assumptions.length > 0 && (
                  <div className="rounded-lg border border-amber/30 bg-amber-50/60 px-3 py-2" data-testid="detail-assumptions">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-amber">What the agent assumed</div>
                    <ul className="mt-1 list-disc pl-4 text-[12.5px]">{detail.answer.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
                  </div>
                )}
                {detail.answer.attempts.map((a, i) => (
                  <div key={i}>
                    <div className="mb-1 text-[11.5px] font-semibold">{i === 0 ? "The agent's query" : "The repair"}{!a.check.ok && `: refused (${a.check.reasons.join("; ")})`}{a.error && `: ${a.error}`}</div>
                    <Sql sql={a.sql} tone={a.check.ok && !a.error ? "plain" : "refused"} />
                  </div>
                ))}
                <div className="grid grid-cols-2 gap-3">
                  <div><div className="mb-1 text-[11.5px] font-semibold">The bank's answer</div>
                    {detail.expected.rows.length ? <ResultTable columns={detail.expected.columns} rows={detail.expected.rows} max={8} /> : <div className="text-[12px] text-ink-2">The warehouse cannot answer this.</div>}</div>
                  <div><div className="mb-1 text-[11.5px] font-semibold">The agent's answer</div>
                    {detail.answer.status === "answered" ? <ResultTable columns={detail.answer.columns} rows={detail.answer.rows} max={8} /> : <div className="text-[12px] text-ink-2">{detail.answer.cannot_answer || detail.answer.status}</div>}</div>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
