// Shared parts of the Agent runs screen: a run step by step, an approval card, and what CaseFlow Classic recorded.
import { Check, ExternalLink, Hand, Loader2, OctagonX, ShieldAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type AgentRun, type AgentStatus, type Approval9, type CaseflowLog } from "../../api";
import { Button, Card, Chip } from "../../components/ui";

export const LIVE = ["running", "waiting_approval"];

export function StatusChip({ status, testId }: { status: string; testId?: string }) {
  const tone = ({ recorded: "teal", proposed: "teal", running: "navy", waiting_approval: "amber", handed_back: "amber", stopped: "ember",
    rejected: "ember", error: "ember" } as const)[status as "recorded"] ?? "mist";
  const label = ({ waiting_approval: "waiting for approval", handed_back: "handed back" } as Record<string, string>)[status] ?? status;
  return <span data-testid={testId}><Chip tone={tone}>{label}</Chip></span>;
}

function DecisionChip({ d }: { d: string }) {
  if (!d || d === "allow") return <span className="text-[10.5px] text-ink-3">allowed</span>;
  const tone = d === "approved" || d === "finish" ? "teal" : d === "stopped" || d === "denied" || d === "rejected" || d === "error" ? "ember" : "amber";
  return <Chip tone={tone}>{d}</Chip>;
}

const argText = (tool: string, a: Record<string, any>) =>
  tool === "click" ? `"${a.name}"` : tool === "type" ? `${a.field}: "${String(a.text).slice(0, 60)}${String(a.text).length > 60 ? "…" : ""}"`
    : tool === "choose" ? `${a.field}: ${a.option}` : tool === "finish" ? `${a.result}` : Object.values(a).map(String).join(", ").slice(0, 80);

export function TicketChips({ st }: { st: AgentStatus | null }) {
  if (!st) return null;
  const names = { "ENG-901": "find by name", "ENG-902": "run limits", "ENG-903": "approval gate" } as const;
  return (
    <div className="flex flex-wrap gap-1.5">
      {(Object.keys(names) as (keyof typeof names)[]).map((t) => (
        <span key={t} data-testid={`ticket-${t}`}><Chip tone={st.tickets[t] ? "teal" : "amber"}>{st.tickets[t] ? <Check size={11} /> : null}{t} {names[t]}{st.tickets[t] ? "" : ": not built"}</Chip></span>
      ))}
    </div>
  );
}

export function ApprovalCard({ a, onDone, compact }: { a: Approval9; onDone?: () => void; compact?: boolean }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const decide = async (decision: "approve" | "reject") => {
    setBusy(decision); setErr("");
    try { await api.post(`/api/agent/approvals/${a.id}`, { decision, note }); onDone?.(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(""); }
  };
  return (
    <div data-testid={`approval-${a.ticket_id}`} className="rounded-xl border-2 border-amber bg-amber-50/60 p-4">
      <div className="flex items-center gap-2 text-[13.5px] font-semibold"><ShieldAlert size={16} className="text-amber" />
        The agent asks to press <span className="rounded bg-white px-1.5 font-mono text-[12px]">{a.target}</span> in CaseFlow Classic for {a.ticket_id}</div>
      <div className="mt-1 text-[12px] text-ink-2">This writes to the bank's system of record, in the name of <b>{a.person}</b>. Approve exactly what is shown, or reject it.</div>
      <div className={`mt-3 grid gap-4 ${compact ? "" : "grid-cols-[1fr_360px]"}`}>
        <div>
          <table className="w-full text-[12.5px]" data-testid="approval-shows"><tbody>
            {a.shows.map(([k, v]) => <tr key={k} className="border-t border-amber/20"><td className="w-[110px] py-1.5 pr-2 font-semibold text-ink-2">{k}</td><td className="py-1.5">{v}</td></tr>)}
          </tbody></table>
          <div className="mt-2 rounded-lg bg-white px-3 py-2 text-[12px]"><span className="font-semibold">The agent's reason: </span><span className="italic">{a.reason}</span></div>
          <div className="mt-2 flex flex-wrap gap-1 text-[11px] text-ink-2">Read first: {a.evidence.map((e) => <span key={e} className="rounded bg-white px-1.5 py-0.5 font-mono">{e}</span>)}</div>
          {a.status === "pending" ? (
            <div className="mt-3 flex items-center gap-2">
              <input data-testid={`approval-note-${a.ticket_id}`} value={note} onChange={(e) => setNote(e.target.value)} placeholder="A note (why you reject, say)"
                className="h-9 flex-1 rounded-lg border border-black/10 bg-white px-3 text-[12.5px]" />
              <Button testId={`approve-${a.ticket_id}`} onClick={() => decide("approve")} disabled={!!busy}>{busy === "approve" ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Approve</Button>
              <Button testId={`reject-${a.ticket_id}`} variant="secondary" onClick={() => decide("reject")} disabled={!!busy}>{busy === "reject" ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />} Reject</Button>
            </div>
          ) : <div className="mt-3 text-[12px]"><StatusChip status={a.status === "approved" ? "recorded" : "rejected"} /> {a.status} by {a.decided_by}{a.note && `: ${a.note}`}</div>}
          {err && <div className="mt-2 text-[12px] text-ember">{err}</div>}
        </div>
        {!compact && a.shot && <img src={`/api/agent/runs/${a.run_id}/shots/${a.shot.split("/").pop()}`} className="w-full rounded-lg border border-black/10" alt="The confirm screen" />}
      </div>
    </div>
  );
}

export function RunView({ runId, onEnd }: { runId: string; onEnd?: () => void }) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [pending, setPending] = useState<Approval9[]>([]);
  const [shot, setShot] = useState<number | null>(null);
  useEffect(() => {
    let alive = true, ended = false;
    const tick = async () => {
      try {
        const r = await api.get<AgentRun>(`/api/agent/runs/${runId}`);
        if (!alive) return;
        setRun(r);
        if (r.status === "waiting_approval") {
          const ap = await api.get<{ pending: Approval9[] }>("/api/agent/approvals");
          setPending(ap.pending.filter((a) => a.run_id === runId));
        } else setPending([]);
        if (!LIVE.includes(r.status) && !ended) { ended = true; onEnd?.(); }
      } catch { /* the run file appears a moment after it starts */ }
    };
    tick();
    const t = setInterval(tick, 700);
    return () => { alive = false; clearInterval(t); };
  }, [runId]);
  if (!run) return <Card className="p-4 text-[12.5px] text-ink-3"><Loader2 size={13} className="mr-1 inline animate-spin" /> Starting the run…</Card>;
  const shots = run.steps.filter((s) => s.shot);
  const shown = run.steps.find((s) => s.n === shot && s.shot) ?? shots[shots.length - 1];
  const tokens = run.tokens_in + run.tokens_out;
  return (
    <div className="space-y-3" data-testid="run-view">
      <Card className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]">
          <span className="text-[15px] font-semibold">{run.ticket_id}</span>
          <StatusChip status={run.status} testId="run-status" />
          {run.outcome && <span data-testid="run-outcome">{run.outcome} {run.reason_code && <span className="text-ink-2">({run.reason_code})</span>}</span>}
          {run.reference && <span className="font-mono text-[12px]" data-testid="run-reference">{run.reference}</span>}
          <span className="ml-auto text-[11.5px] text-ink-2" data-testid="run-limits">{run.steps.length} steps · {tokens.toLocaleString()} tokens · {run.cost_usd != null ? `$${run.cost_usd.toFixed(4)}` : ""} · as {run.person} · {run.prompt}</span>
        </div>
        {run.stop_reason && <div data-testid="run-stop" className="mt-2 flex items-center gap-2 rounded-lg bg-ember-50 px-3 py-2 text-[12.5px]"><OctagonX size={14} className="text-ember" /> {run.stop_reason}</div>}
        {run.summary && !run.stop_reason && <div data-testid="run-summary" className="mt-2 flex items-center gap-2 text-[12.5px] text-ink-2"><Hand size={13} /> {run.summary}</div>}
      </Card>
      {pending.map((a) => <ApprovalCard key={a.id} a={a} compact />)}
      <div className="grid grid-cols-[1fr_440px] gap-3">
        <Card className="overflow-hidden" testId="run-steps">
          <table className="w-full text-left text-[12px]">
            <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="w-8 px-3 py-1.5">#</th><th>What the agent thought, and did</th><th className="w-[88px]">Gate</th></tr></thead>
            <tbody>
              {run.steps.map((s) => (
                <tr key={s.n} data-testid={`step-${s.n}`} onClick={() => s.shot && setShot(s.n)}
                  className={`border-t border-black/[0.05] align-top ${s.shot ? "cursor-pointer hover:bg-mist/60" : ""} ${shown?.n === s.n ? "bg-teal-50/60" : ""}`}>
                  <td className="px-3 py-1.5 font-mono text-[11px] text-ink-3">{s.n}</td>
                  <td className="py-1.5 pr-2">
                    <div className="italic text-ink-2">{s.thought}</div>
                    <div className="mt-0.5"><span className="rounded bg-mist px-1.5 py-0.5 font-mono text-[11px]">{s.tool}</span> <span className="text-[11.5px]">{argText(s.tool, s.args)}</span>
                      {s.tool === "click" && s.target && s.target !== s.args.name && <span className="ml-1 font-semibold text-ember">pressed “{s.target}”</span>}</div>
                    {(s.decision === "denied" || s.decision === "error" || s.decision === "stopped" || s.decision === "rejected" || s.observation.includes("CHECK FAILED") || s.observation.includes("CaseFlow saved it")) &&
                      <div className="mt-0.5 text-[11.5px] text-ink">{s.observation.split("\n").filter((l) => /Refused|error|CHECK|saved it|Rejected|Repeating|limit|budget|Expired/i.test(l)).join(" · ") || s.observation.slice(0, 160)}</div>}
                  </td>
                  <td className="py-1.5 pr-3"><DecisionChip d={s.decision} /></td>
                </tr>
              ))}
              {LIVE.includes(run.status) && <tr><td /><td className="py-2 text-[12px] text-ink-3"><Loader2 size={12} className="mr-1 inline animate-spin" /> {run.status === "waiting_approval" ? "Waiting for your approval…" : "Working…"}</td><td /></tr>}
            </tbody>
          </table>
        </Card>
        <Card className="self-start overflow-hidden" testId="run-shot">
          <div className="border-b border-black/[0.05] px-3 py-2 text-[12px] font-semibold">CaseFlow Classic, as the agent saw it {shown && <span className="font-normal text-ink-3">· step {shown.n}</span>}</div>
          {shown ? <img src={`/api/agent/runs/${run.id}/shots/${shown.shot}`} className="w-full" alt={`Step ${shown.n}`} />
            : <div className="p-4 text-[12px] text-ink-3">The agent has not opened CaseFlow Classic yet.</div>}
        </Card>
      </div>
    </div>
  );
}

export function CaseflowCard({ refresh }: { refresh: number }) {
  const [log, setLog] = useState<CaseflowLog | null>(null);
  useEffect(() => { api.get<CaseflowLog>("/api/agent/caseflow").then(setLog).catch(() => setLog(null)); }, [refresh]);
  return (
    <Card className="overflow-hidden" testId="caseflow-log">
      <div className="flex items-center px-4 py-3">
        <div className="flex-1">
          <div className="text-[13.5px] font-semibold">What CaseFlow Classic recorded</div>
          <div className="text-[12px] text-ink-2">Read from the bank's side: the outcome, and who CaseFlow thinks recorded it.</div>
        </div>
        {log && <a href={log.url} target="_blank" rel="noreferrer" data-testid="legacy-link" className="flex items-center gap-1 text-[12px] font-semibold text-teal">Open CaseFlow Classic <ExternalLink size={12} /></a>}
      </div>
      <table className="w-full text-left text-[12px]">
        <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Time</th><th>Case</th><th>Outcome</th><th>Reference</th><th>Recorded by</th></tr></thead>
        <tbody>
          {(log?.outcomes ?? []).slice(0, 8).map((o) => (
            <tr key={o.reference} className="border-t border-black/[0.05]">
              <td className="px-4 py-1.5 font-mono text-[11px] text-ink-3">{o.at.slice(11)}</td><td className="font-mono text-[11.5px]">{o.case_ref}</td>
              <td className={o.outcome === "Case withdrawn" ? "font-semibold text-ember" : ""}>{o.outcome} {o.reason && <span className="text-ink-3">({o.reason})</span>}</td>
              <td className="font-mono text-[11.5px]">{o.reference}</td><td><b>{o.by}</b>{o.via && <span className="text-ink-2"> via {o.via}</span>}</td>
            </tr>
          ))}
          {log && !log.outcomes.length && <tr><td colSpan={5} className="px-4 py-3 text-ink-3">Nothing recorded yet.</td></tr>}
        </tbody>
      </table>
    </Card>
  );
}
