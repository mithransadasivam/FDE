// My queue: the agent works every one of my open exceptions in turn; I approve or reject each write. Scored against the bank.
import { ListChecks, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Approval9, type QueueView } from "../../api";
import { Button, Card, Chip, Kpi } from "../../components/ui";
import { ApprovalCard, CaseflowCard, StatusChip } from "./parts";
import { SignInFirst, useAgentStatus } from "./RunTab";

export default function QueueTab() {
  const st = useAgentStatus();
  const [q, setQ] = useState<QueueView | null>(null);
  const [pending, setPending] = useState<Approval9[]>([]);
  const [err, setErr] = useState("");
  const load = async () => {
    const x = await api.get<{ queue: QueueView | null }>("/api/agent/queue");
    setQ(x.queue);
    const ap = await api.get<{ pending: Approval9[] }>("/api/agent/approvals");
    setPending(ap.pending.filter((a) => x.queue?.runs.some((r) => r.id === a.run_id)));
  };
  useEffect(() => { load(); const t = setInterval(load, 1000); return () => clearInterval(t); }, []);
  if (st && !st.person) return <SignInFirst />;
  const go = async () => { setErr(""); try { await api.post("/api/agent/queue"); await load(); } catch (e: any) { setErr(e.message); } };
  const sc = q?.scorecard;
  return (
    <div className="space-y-4">
      <Card className="flex items-center gap-4 p-4">
        <div className="flex-1">
          <div className="text-[13.5px] font-semibold">Run my queue</div>
          <div className="text-[12px] text-ink-2">The agent works each of {st?.person?.name ?? "your"}'s open exceptions in turn, as you. Each write waits for you here.</div>
        </div>
        <Button testId="queue-go" onClick={go} disabled={q?.status === "running"}>{q?.status === "running" ? <Loader2 size={13} className="animate-spin" /> : <ListChecks size={13} />} Run my queue</Button>
      </Card>
      {err && <div className="rounded-lg bg-ember-50 px-3 py-2 text-[12.5px]">{err}</div>}
      {pending.map((a) => <ApprovalCard key={a.id} a={a} onDone={load} />)}
      {q && (
        <div className="grid grid-cols-[1fr_300px] gap-4">
          <Card className="overflow-hidden" testId="queue-table">
            <table className="w-full text-left text-[12.5px]">
              <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Exception</th><th>How the run ended</th><th>The bank expects</th><th className="w-[70px]" /></tr></thead>
              <tbody>
                {q.tickets.map((t) => {
                  const r = q.runs.find((x) => x.ticket_id === t);
                  const s = sc?.rows.find((x) => x.ticket_id === t);
                  return (
                    <tr key={t} data-testid={`queue-row-${t}`} className="border-t border-black/[0.05] align-top">
                      <td className="px-4 py-2 font-mono text-[12px]">{t}<div className="font-sans text-[11px] text-ink-3">{r ? `${r.steps} steps` : "waiting"}</div></td>
                      <td className="py-2 pr-2">{r ? <><StatusChip status={r.status} /> {r.outcome} <span className="font-mono text-[11px]">{r.reference}</span>
                        {r.stop_reason && <div className="text-[11.5px] text-ink-2">{r.stop_reason}</div>}</> : <span className="text-ink-3">not started</span>}</td>
                      <td className="py-2 pr-2 text-[12px]">{s ? <><b>{s.expected_end}</b> {s.expected_outcome}<div className="text-[11px] text-ink-2">{s.why}</div></> : ""}</td>
                      <td className="py-2 pr-4">{s && <Chip tone={s.ok ? "teal" : "ember"}>{s.ok ? "as expected" : "differs"}</Chip>}</td>
                    </tr>);
                })}
              </tbody>
            </table>
          </Card>
          <div className="space-y-3" data-testid="queue-summary">
            <Kpi label="As the bank expects" value={sc ? `${sc.ok} of ${sc.total}` : "…"} tone={sc && sc.ok === sc.total ? "teal" : "amber"} sub={sc ? "data/Day09_Slide26_queue_expected.csv" : "the queue is running"} />
            <Kpi label="Steps" value={q.runs.reduce((a, r) => a + r.steps, 0)} sub={`across ${q.runs.length} runs`} />
            <Kpi label="Cost of the queue" value={`$${q.cost_usd.toFixed(4)}`} sub={`${st?.model ?? ""} prices`} />
          </div>
        </div>
      )}
      <CaseflowCard refresh={q?.runs.length ?? 0} />
    </div>
  );
}
