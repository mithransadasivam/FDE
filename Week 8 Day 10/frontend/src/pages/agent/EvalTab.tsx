// Evaluation (homework): the agent on the bank's 20 evaluation cases, as Helen, in shadow mode. Each run is scored by score_run().
import { FlaskConical, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type EvalView9 } from "../../api";
import { Button, Card, Chip, NotBuilt } from "../../components/ui";
import { useAgentStatus } from "./RunTab";

const CHECKS = ["end", "outcome", "read_first", "no_write", "steps"];

export default function EvalTab() {
  const st = useAgentStatus();
  const [v, setV] = useState<EvalView9 | null>(null);
  const [prompt, setPrompt] = useState("ops_v1");
  const [show, setShow] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const load = () => api.get<EvalView9>("/api/agent/evals").then(setV);
  useEffect(() => { load(); const t = setInterval(load, 1500); return () => clearInterval(t); }, []);
  const go = async () => { setErr(""); try { await api.post("/api/agent/evals", { prompt }); load(); } catch (e: any) { setErr(e.message); } };
  const run = v?.saved.find((s) => s.prompt === (show ?? v?.saved[v.saved.length - 1]?.prompt));
  return (
    <div className="space-y-4">
      {v && !v.gate_built && <NotBuilt ticket="ENG-903">Shadow mode relies on the gate asking before Confirm. Without it, the evaluation runs would write to CaseFlow Classic.</NotBuilt>}
      <Card className="flex items-center gap-4 p-4">
        <div className="flex-1">
          <div className="text-[13.5px] font-semibold">The 20 evaluation cases, in shadow mode</div>
          <div className="text-[12px] text-ink-2">As {v?.run_as}: every approval is refused and recorded, so the agent stops at CaseFlow's confirm screen and writes nothing.</div>
        </div>
        <select data-testid="eval-prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} className="h-9 rounded-lg border border-black/10 px-2 text-[12.5px]">
          {(st?.prompts ?? ["ops_v1"]).map((p) => <option key={p}>{p}</option>)}
        </select>
        <Button testId="eval-go" onClick={go} disabled={!!v?.running || !v?.gate_built}>{v?.running ? <Loader2 size={13} className="animate-spin" /> : <FlaskConical size={13} />} Run the 20</Button>
      </Card>
      {(err || v?.error) && <div className="rounded-lg bg-ember-50 px-3 py-2 text-[12.5px]">{err || v?.error}</div>}
      {v?.running && <Card className="p-3 font-mono text-[11.5px] text-ink-2" testId="eval-log">{v.log.slice(-6).map((l) => <div key={l}>{l}</div>)}</Card>}
      <div className="grid grid-cols-4 gap-3" data-testid="eval-summary">
        {v?.saved.map((s) => (
          <button key={s.prompt} onClick={() => setShow(s.prompt)} data-testid={`eval-summary-${s.prompt}`}
            className={`rounded-xl border bg-white px-4 py-3 text-left ${run?.prompt === s.prompt ? "border-navy" : "border-black/[0.06]"}`}>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">{s.prompt}</div>
            <div className={`mt-1 text-[22px] font-semibold ${s.passed === s.total ? "text-teal" : "text-amber"}`}>{s.scored ? `${s.passed} of ${s.total}` : "not scored"}</div>
            <div className="text-[11.5px] text-ink-2">{s.tokens_in.toLocaleString()} tokens in · ${s.cost_usd.toFixed(4)}</div>
          </button>
        ))}
      </div>
      {run && (
        <Card className="overflow-hidden" testId="eval-table">
          <table className="w-full text-left text-[12px]">
            <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-3 py-1.5">Case</th><th>Expected</th><th>The run</th>{CHECKS.map((c) => <th key={c} className="w-[62px]">{c.replace("_", " ")}</th>)}</tr></thead>
            <tbody>{run.results.map((r) => (
              <tr key={r.id} data-testid={`eval-row-${r.id}`} className={`border-t border-black/[0.05] align-top ${r.score.passed === false ? "bg-ember-50/40" : ""}`}>
                <td className="px-3 py-1.5"><span className="font-mono text-[11.5px]">{r.id} {r.ticket_id}</span><div className="text-[10.5px] text-ink-3">{r.kind.replace(/_/g, " ")}</div></td>
                <td className="py-1.5 pr-2">{r.expected_end === "handed_back" ? <i>hand back</i> : `${r.expected_outcome} (${r.expected_reason})`}{r.note && <div className="text-[10.5px] text-ink-3">{r.note}</div>}</td>
                <td className="py-1.5 pr-2">{r.status} {r.outcome && `· ${r.outcome} (${r.reason_code})`}{r.stop_reason && <div className="text-[10.5px] text-ink-3">{r.stop_reason}</div>}</td>
                {CHECKS.map((c) => <td key={c} className="py-1.5">{r.score.checks?.[c] === undefined ? "–" : <Chip tone={r.score.checks[c] ? "teal" : "ember"}>{r.score.checks[c] ? "✓" : "✗"}</Chip>}</td>)}
              </tr>))}</tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
