// My queue: my four exceptions as case workflows, start to end, with every write counted against the bank's expectations.
import { ListChecks, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Approval9, type QueueState10 } from "../../api";
import { Button, Card, Chip, Kpi } from "../../components/ui";
import { ApprovalCard } from "../agent/parts";
import { SignInFirst } from "../agent/RunTab";
import { StateChip, WorkerBar, useWorkflowStatus } from "./parts";

export default function QueueTab10() {
  const st = useWorkflowStatus();
  const [q, setQ] = useState<QueueState10 | null>(null);
  const [pending, setPending] = useState<Approval9[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const load = async () => {
    const x = await api.get<QueueState10>("/api/workflow/queue");
    setQ(x);
    const ap = await api.get<{ pending: Approval9[] }>("/api/agent/approvals");
    setPending(ap.pending.filter((a: any) => x.rows.some((r) => r.key === a.workflow_id)));
  };
  useEffect(() => { load(); const t = setInterval(load, 1000); return () => clearInterval(t); }, []);
  if (st && !st.person) return <SignInFirst />;
  const go = async () => { setBusy(true); setErr(""); try { await api.post("/api/workflow/queue"); await load(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  const running = !!q?.rows.length && !q.done;
  return (
    <div className="space-y-4">
      <WorkerBar st={st} />
      <Card className="flex items-center gap-4 p-4">
        <div className="flex-1">
          <div className="text-[13.5px] font-semibold">Run my queue as case workflows</div>
          <div className="text-[12px] text-ink-2">All four of {st?.person?.name ?? "your"}'s exceptions at once. Each outcome waits for you here; the applicants reply on their own schedule (data/Day10_Slide26_applicant_replies.json).</div>
        </div>
        <Button testId="queue10-go" onClick={go} disabled={busy || running}>{busy || running ? <Loader2 size={13} className="animate-spin" /> : <ListChecks size={13} />} Run my queue</Button>
      </Card>
      {err && <div className="rounded-lg bg-ember-50 px-3 py-2 text-[12.5px]">{err}</div>}
      {pending.map((a) => <ApprovalCard key={a.id} a={a} compact />)}
      {q && q.rows.length > 0 && (
        <div className="grid grid-cols-[1fr_280px] gap-4">
          <Card className="overflow-hidden" testId="queue10-table">
            <table className="w-full text-left text-[12px]">
              <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Exception</th><th>Now</th><th>Requests · reminders · escalations · CaseFlow outcomes</th><th>The bank expects</th><th className="w-[80px]" /></tr></thead>
              <tbody>{q.rows.map((r) => (
                <tr key={r.key} data-testid={`queue10-row-${r.ticket_id}`} className="border-t border-black/[0.05] align-top">
                  <td className="px-4 py-2 font-mono text-[12px]">{r.ticket_id}<div className="font-sans text-[11px] text-ink-3">day {r.day.toFixed(1)}{r.recovered > 0 ? ` · after ${r.recovered} crash${r.recovered === 1 ? "" : "es"}` : ""}</div></td>
                  <td className="py-2 pr-2"><StateChip state={r.state} /><div className="mt-0.5 max-w-[260px] text-[11px] text-ink-2">{r.last}</div></td>
                  <td className="py-2 pr-2 font-mono text-[12px]">{r.requests} · {r.reminders} · {r.escalations} · {r.caseflow_outcomes}</td>
                  <td className="py-2 pr-2 text-[11.5px]"><b>{r.expected.expected_end}</b> <span className="font-mono">{r.expected.requests} · {r.expected.reminders} · {r.expected.escalations} · {r.expected.caseflow_outcomes}</span>
                    <div className="text-[11px] text-ink-2">{r.expected.why}</div></td>
                  <td className="py-2 pr-4">{r.done ? <Chip tone={r.ok ? "teal" : "ember"}>{r.ok ? "as expected" : "differs"}</Chip> : <Loader2 size={13} className="animate-spin text-ink-3" />}</td>
                </tr>))}</tbody>
            </table>
          </Card>
          <div className="space-y-3" data-testid="queue10-summary">
            <Kpi label="As the bank expects" value={q.done ? `${q.ok} of ${q.total}` : "…"} tone={q.done && q.ok === q.total ? "teal" : "amber"} sub={q.done ? "data/Day10_Slide26_queue_expected.csv" : "the cases are running"} />
            <Kpi label="Worker crashes" value={st?.worker.crashes.filter((c) => q.started_at && c.at >= q.started_at).length ?? 0} sub="during this queue" />
            <Kpi label="Longest case" value={`${Math.max(...q.rows.map((r) => r.day)).toFixed(1)} days`} sub={`one day = ${st?.worker.day_seconds ?? ""} s`} />
          </div>
        </div>
      )}
    </div>
  );
}
