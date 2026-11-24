// Shared parts of the Workflows screen: the worker, a case's clock and timeline, and the bank's records for a case.
import { AlertTriangle, Check, CircleDot, Clock3, FileCheck2, Loader2, Mail, MailWarning, OctagonX, PlayCircle, RotateCcw, Send, ShieldCheck, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type WfCase, type CaseEvent, type WorkflowStatus } from "../../api";
import { Button, Card, Chip } from "../../components/ui";
import { ApprovalCard } from "../agent/parts";

export function useWorkflowStatus(every = 1500) {
  const [st, setSt] = useState<WorkflowStatus | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => api.get<WorkflowStatus>("/api/workflow/status").then((s) => alive && setSt(s)).catch(() => alive && setSt(null));
    load();
    const t = setInterval(load, every);
    return () => { alive = false; clearInterval(t); };
  }, [every]);
  return st;
}

const STATE: Record<string, { tone: "teal" | "amber" | "ember" | "navy" | "mist"; label: string }> = {
  completed: { tone: "teal", label: "completed" }, recorded: { tone: "teal", label: "recorded" }, escalated: { tone: "amber", label: "escalated" },
  waiting_approval: { tone: "amber", label: "waiting for approval" }, waiting_documents: { tone: "navy", label: "waiting for the applicant" },
  stopped: { tone: "ember", label: "stopped" }, handed_back: { tone: "amber", label: "handed back" }, rejected: { tone: "ember", label: "rejected" },
  expired: { tone: "ember", label: "approval expired" }, error: { tone: "ember", label: "error" },
};

export function StateChip({ state, testId }: { state: string; testId?: string }) {
  const s = STATE[state] ?? { tone: "navy" as const, label: state.replace(/_/g, " ") || "running" };
  return <span data-testid={testId}><Chip tone={s.tone}>{s.label}</Chip></span>;
}

export function TicketChips10({ st }: { st: WorkflowStatus | null }) {
  if (!st) return null;
  const names = { "ENG-1001": "propose, wait, write", "ENG-1002": "a durable clock", "ENG-1003": "every write once" } as const;
  return (
    <div className="flex flex-wrap gap-1.5" data-testid="wf-tickets">
      {(Object.keys(names) as (keyof typeof names)[]).map((t) => (
        <span key={t} data-testid={`ticket-${t}`}><Chip tone={st.tickets[t] ? "teal" : "amber"}>{st.tickets[t] ? <Check size={11} /> : null}{t} {names[t]}{st.tickets[t] ? "" : ": not built"}</Chip></span>
      ))}
    </div>
  );
}

export function WorkerBar({ st, onCrash }: { st: WorkflowStatus | null; onCrash?: () => void }) {
  const [busy, setBusy] = useState(false);
  if (!st) return null;
  const w = st.worker;
  const crash = async () => { setBusy(true); try { await api.post("/api/workflow/crash", { point: "now" }); onCrash?.(); } finally { setTimeout(() => setBusy(false), 1500); } };
  return (
    <Card className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5" testId="worker-bar">
      <span className="flex items-center gap-2 text-[13px] font-semibold">
        <span className={`h-2.5 w-2.5 rounded-full ${w.up ? "bg-teal" : "animate-pulse bg-ember"}`} />
        <span data-testid="worker-state">{w.up ? "Workflow worker up" : "Workflow worker down: starting again…"}</span>
      </span>
      <span className="text-[12px] text-ink-2">pid {w.pid ?? "–"} · started {w.starts} time{w.starts === 1 ? "" : "s"} · <span data-testid="worker-crashes">{w.crashes.length} crash{w.crashes.length === 1 ? "" : "es"}</span></span>
      <span className="flex items-center gap-1 text-[12px] text-ink-2"><Clock3 size={13} /> One course day = <b data-testid="day-seconds">{w.day_seconds}</b> s</span>
      {w.armed.length > 0 && <span className="text-[12px]" data-testid="worker-armed"><Chip tone="amber"><Zap size={11} /> armed: {w.armed.map((a) => `${a.point}${a.ticket !== "*" ? " · " + a.ticket : ""}`).join(", ")}</Chip></span>}
      <span className="ml-auto"><Button testId="crash-now" variant="secondary" onClick={crash} disabled={busy || !w.up}>{busy ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />} Crash the worker now</Button></span>
    </Card>
  );
}

// Events the console's API writes (not the worker): they do not tell us which worker ran
const API_KINDS = new Set(["start", "decided"]);
/** The indexes of events that a new worker process wrote after an earlier one: the worker crashed and started again. */
export function restarts(events: CaseEvent[]): Set<number> {
  const out = new Set<number>();
  let last: number | null = null;
  events.forEach((e, i) => {
    if (API_KINDS.has(e.kind)) return;
    if (last !== null && e.pid !== last) out.add(i);
    last = e.pid;
  });
  return out;
}

const ICON: Record<string, any> = {
  start: PlayCircle, propose: CircleDot, proposed: ShieldCheck, decided: Check, apply: FileCheck2, recorded: FileCheck2, already: RotateCcw,
  send_request: Send, send_reminder: MailWarning, sent: Mail, replayed: RotateCcw, documents: FileCheck2, escalate: AlertTriangle,
  escalated: AlertTriangle, expired: OctagonX, agent_ended: OctagonX, end: Check,
};
const TONE: Record<string, string> = {
  recorded: "text-teal", already: "text-teal", replayed: "text-teal", documents: "text-teal", end: "text-teal", sent: "text-navy",
  escalate: "text-amber", escalated: "text-amber", expired: "text-ember", agent_ended: "text-ember", proposed: "text-amber", decided: "text-teal",
};

export function CaseClock({ c, policy }: { c: WfCase; policy: { reminder_after_days: number; escalate_after_days: number } }) {
  const req = c.events.find((e) => e.kind === "sent" || e.kind === "replayed");
  const end = Math.max(9, Math.ceil((c.day || 0) + 1));
  const x = (d: number) => `${Math.min(100, (d / end) * 100)}%`;
  const marks = [
    ...c.effects.messages.map((m) => ({ d: m.day ?? 0, label: m.kind === "request" ? `Request ${m.id}` : `Reminder ${m.id}`, tone: m.kind === "request" ? "bg-navy" : "bg-amber", kind: m.kind })),
    ...c.events.filter((e) => ["documents", "escalated", "recorded", "already", "expired"].includes(e.kind))
      .map((e) => ({ d: e.day, label: e.kind === "documents" ? "Documents" : e.kind === "escalated" ? "Escalated" : e.kind === "expired" ? "Expired" : "Recorded", tone: e.kind === "escalated" ? "bg-ember" : e.kind === "expired" ? "bg-ember" : "bg-teal", kind: e.kind })),
  ];
  const rs = restarts(c.events);
  const crashes = c.events.filter((_, i) => rs.has(i));
  return (
    <Card className="px-4 pb-4 pt-3" testId="case-clock">
      <div className="mb-6 flex items-center gap-2 text-[12.5px] font-semibold">The case's clock <span className="font-normal text-ink-3">· course days since {c.person} started it</span>
        <span className="ml-auto font-normal text-ink-2">day <b data-testid="case-day">{c.day.toFixed(1)}</b></span></div>
      <div className="relative mx-2 h-10">
        <div className="absolute left-0 right-0 top-4 h-1.5 rounded-full bg-mist" />
        <div className="absolute left-0 top-4 h-1.5 rounded-full bg-navy/25" style={{ width: x(c.day) }} />
        {req && !c.end && !c.events.some((e) => e.kind === "documents") && <>
          <div className="absolute top-0 h-10 border-l-2 border-dashed border-amber/70" style={{ left: x(req.day + policy.reminder_after_days) }} title="Reminder due" />
          <div className="absolute -top-5 -translate-x-1/2 whitespace-nowrap text-[10px] font-semibold text-amber" style={{ left: x(req.day + policy.reminder_after_days) }}>reminder due</div>
          <div className="absolute top-0 h-10 border-l-2 border-dashed border-ember/70" style={{ left: x(req.day + policy.escalate_after_days) }} title="Escalation due" />
          <div className="absolute -top-5 -translate-x-1/2 whitespace-nowrap text-[10px] font-semibold text-ember" style={{ left: x(req.day + policy.escalate_after_days) }}>escalation due</div>
        </>}
        {crashes.map((e, i) => <div key={i} className="absolute top-1 -translate-x-1/2 text-ember" style={{ left: x(e.day) }} title="The worker crashed and started again"><Zap size={14} /></div>)}
        {marks.map((m, i) => (
          <div key={i} data-testid={`clock-${m.kind}`} className="absolute top-3 -translate-x-1/2" style={{ left: x(m.d) }} title={`${m.label} · day ${m.d}`}>
            <div className={`h-3.5 w-3.5 rounded-full border-2 border-white ${m.tone}`} />
          </div>
        ))}
      </div>
      <div className="mx-2 flex justify-between text-[10.5px] text-ink-3">{Array.from({ length: end + 1 }, (_, i) => <span key={i}>{i}</span>)}</div>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-ink-2">
        {marks.map((m, i) => <span key={i} className="flex items-center gap-1"><span className={`h-2.5 w-2.5 rounded-full ${m.tone}`} />{m.label} · day {m.d}</span>)}
        {crashes.length > 0 && <span className="flex items-center gap-1 text-ember"><Zap size={11} /> worker crashed {crashes.length}×</span>}
      </div>
    </Card>
  );
}

export function Timeline({ events }: { events: CaseEvent[] }) {
  const rs = restarts(events);
  return (
    <Card className="overflow-hidden" testId="case-timeline">
      <div className="border-b border-black/[0.05] px-4 py-2 text-[12.5px] font-semibold">What the workflow did <span className="font-normal text-ink-3">· its own log, one line each time a step starts</span></div>
      <div>
        {events.map((e, i) => {
          const I = ICON[e.kind] ?? CircleDot;
          const restarted = rs.has(i);
          return (
            <div key={i}>
              {restarted && <div data-testid="timeline-restart" className="flex items-center gap-2 border-t border-ember/20 bg-ember-50/60 px-4 py-1 text-[11px] font-semibold text-ember"><Zap size={11} /> The worker crashed; a new worker carried on</div>}
              <div data-testid={`event-${e.kind}`} className="flex items-start gap-3 border-t border-black/[0.04] px-4 py-1.5 text-[12px]">
                <span className="w-[52px] shrink-0 pt-px text-right font-mono text-[11px] text-ink-3">day {e.day.toFixed(1)}</span>
                <I size={13} className={`mt-0.5 shrink-0 ${TONE[e.kind] ?? "text-ink-3"}`} />
                <span className="flex-1">{e.text}</span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export function BankRecords({ c }: { c: WfCase }) {
  const k = c.counts;
  const cell = (label: string, n: number, testId: string) => (
    <div data-testid={testId} className={`rounded-lg px-3 py-2 ${n > 1 && testId !== "count-outcomes" && testId !== "count-comments" ? "bg-ember-50" : "bg-mist"}`}>
      <div className="text-[18px] font-semibold leading-none">{n}</div><div className="mt-1 text-[10.5px] text-ink-2">{label}</div>
    </div>
  );
  return (
    <Card className="p-4" testId="case-writes">
      <div className="text-[12.5px] font-semibold">What the bank's systems hold for {c.ticket_id}</div>
      <div className="text-[11.5px] text-ink-2">Counted from the bank's own records, not from the workflow's log.</div>
      <div className="mt-3 grid grid-cols-5 gap-2">
        {cell("requests to the applicant", k.requests, "count-requests")}{cell("reminders", k.reminders, "count-reminders")}
        {cell("CaseFlow outcomes", k.caseflow_outcomes, "count-outcomes")}{cell("“Outcome recorded” comments", k.outcome_comments, "count-comments")}
        {cell("escalations", k.escalations, "count-escalations")}
      </div>
      {c.effects.messages.length > 0 && (
        <table className="mt-3 w-full text-left text-[11.5px]" data-testid="case-messages">
          <thead className="text-[10px] uppercase tracking-wide text-ink-3"><tr><th className="py-1">Message</th><th>Day</th><th>Sent for</th><th>Idempotency-Key</th></tr></thead>
          <tbody>{c.effects.messages.map((m) => (
            <tr key={m.id} className="border-t border-black/[0.05]"><td className="py-1 font-mono">{m.id} <span className="font-sans">{m.kind}</span></td><td>{m.day}</td>
              <td>{m.by}{m.via && <span className="text-ink-3"> via {m.via}</span>}</td><td className="font-mono text-[10.5px] text-ink-2">{m.key ?? "none"}</td></tr>))}</tbody>
        </table>
      )}
      {c.effects.outcomes.length > 0 && (
        <table className="mt-3 w-full text-left text-[11.5px]" data-testid="case-outcomes">
          <thead className="text-[10px] uppercase tracking-wide text-ink-3"><tr><th className="py-1">CaseFlow outcome</th><th>Reference</th><th>Recorded by</th></tr></thead>
          <tbody>{c.effects.outcomes.map((o) => (
            <tr key={o.reference} className="border-t border-black/[0.05]"><td className="py-1">{o.outcome} <span className="text-ink-3">({o.reason})</span></td>
              <td className="font-mono">{o.reference}</td><td>{o.by}{o.via && <span className="text-ink-3"> via {o.via}</span>}</td></tr>))}</tbody>
        </table>
      )}
    </Card>
  );
}

export function CaseView({ caseKey, policy }: { caseKey: string; policy: WorkflowStatus["policy"] | undefined }) {
  const [c, setC] = useState<WfCase | null>(null);
  const [doc, setDoc] = useState("utility_bill");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () => api.get<WfCase>(`/api/workflow/cases/${caseKey}`).then((x) => alive && setC(x)).catch(() => undefined);
    load();
    const t = setInterval(load, 800);
    return () => { alive = false; clearInterval(t); };
  }, [caseKey]);
  if (!c || !policy) return <Card className="p-4 text-[12.5px] text-ink-3"><Loader2 size={13} className="mr-1 inline animate-spin" /> Loading the case…</Card>;
  const pending = c.approvals.filter((a) => a.status === "pending");
  const reply = async () => { setBusy(true); try { await api.post("/api/workflow/applicant-reply", { ticket_id: c.ticket_id, doc_type: doc }); } finally { setBusy(false); } };
  const agentRounds = c.runs.length;
  return (
    <div className="space-y-3" data-testid="case-view">
      <Card className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]">
          <span className="text-[15px] font-semibold" data-testid="case-ticket">{c.ticket_id}</span>
          <StateChip state={c.state} testId="case-state" />
          <span className="font-mono text-[11.5px] text-ink-3">{c.key}</span>
          {c.recovered > 0 && <span data-testid="case-recovered"><Chip tone="amber"><RotateCcw size={11} /> picked up after {c.recovered} crash{c.recovered === 1 ? "" : "es"}</Chip></span>}
          <span className="ml-auto text-[11.5px] text-ink-2" data-testid="case-runs">{agentRounds} agent run{agentRounds === 1 ? "" : "s"} · {c.tokens_in.toLocaleString()} tokens in · ${c.cost_usd.toFixed(4)} · as {c.person}</span>
        </div>
        {!c.end && c.state === "waiting_documents" && (
          <div className="mt-2 flex items-center gap-2 text-[12px]">
            <span className="text-ink-2">Course stand-in: make the applicant reply now</span>
            <select data-testid="reply-doc" value={doc} onChange={(e) => setDoc(e.target.value)} className="h-8 rounded-lg border border-black/10 bg-white px-2 text-[12px]">
              {["utility_bill", "passport", "driving_licence", "bank_statement", "council_tax_bill"].map((d) => <option key={d} value={d}>{d.replace(/_/g, " ")}</option>)}
            </select>
            <Button testId={`reply-${c.ticket_id}`} variant="secondary" onClick={reply} disabled={busy}><Mail size={13} /> Applicant replies</Button>
          </div>
        )}
      </Card>
      {pending.map((a) => <ApprovalCard key={a.id} a={a} compact />)}
      <CaseClock c={c} policy={policy} />
      <div className="grid grid-cols-2 gap-3">
        <Timeline events={c.events} />
        <div className="space-y-3">
          <BankRecords c={c} />
          <Card className="overflow-hidden" testId="case-steps">
            <div className="border-b border-black/[0.05] px-4 py-2 text-[12.5px] font-semibold">The checkpoints DBOS saved <span className="font-normal text-ink-3">· a finished step is never run again</span></div>
            <table className="w-full text-left text-[11.5px]">
              <tbody>{c.steps.map((s) => (
                <tr key={s.n} className="border-t border-black/[0.04]"><td className="w-8 px-4 py-1 font-mono text-ink-3">{s.n}</td>
                  <td className="font-mono">{s.name}</td><td className="pr-4 text-right text-ink-2">{s.done_day != null ? `day ${s.done_day}` : ""}</td></tr>))}
                {!c.steps.length && <tr><td className="px-4 py-2 text-ink-3">No checkpoint yet.</td></tr>}</tbody>
            </table>
          </Card>
        </div>
      </div>
    </div>
  );
}
