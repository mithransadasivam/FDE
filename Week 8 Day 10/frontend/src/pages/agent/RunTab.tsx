// Work one exception: pick one of your KYC exceptions and watch the agent work it, step by step, in CaseFlow Classic.
import { LogIn, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type AgentStatus, type MyException } from "../../api";
import { Button, Card } from "../../components/ui";
import { CaseflowCard, RunView, StatusChip, TicketChips } from "./parts";

export function useAgentStatus() {
  const [st, setSt] = useState<AgentStatus | null>(null);
  useEffect(() => { api.get<AgentStatus>("/api/agent/status").then(setSt).catch(() => setSt(null)); }, []);
  return st;
}

export function SignInFirst() {
  return (
    <Card className="p-5" testId="agent-signin">
      <div className="text-[14px] font-semibold">Sign in with the bank first</div>
      <div className="mt-1 text-[12.5px] text-ink-2">The agent works as the person signed in to the console: the bank's systems apply that person's permissions, and every record names them.</div>
      <a className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-navy px-3 py-2 text-[12.5px] font-semibold text-white" data-testid="agent-sign-in"
        href={`/api/auth/login?next=${encodeURIComponent("/" + window.location.hash)}&origin=${encodeURIComponent(window.location.origin)}`}><LogIn size={13} /> Sign in with the bank</a>
    </Card>
  );
}

const KIND: Record<string, string> = { overdue: "Overdue", applicant_follow_up: "Applicant follow-up", escalation: "Escalation" };

export default function RunTab() {
  const st = useAgentStatus();
  const [mine, setMine] = useState<MyException[]>([]);
  const [runId, setRunId] = useState<string | null>(window.location.hash.split("/")[3] || null);
  const [prompt, setPrompt] = useState("ops_v1");
  const [refresh, setRefresh] = useState(0);
  const [err, setErr] = useState("");
  const load = () => api.get<{ tickets: MyException[] }>("/api/agent/exceptions").then((x) => setMine(x.tickets)).catch((e) => setErr(e.message));
  useEffect(() => { if (st?.person) load(); }, [st?.person?.sub, refresh]);
  if (st && !st.person) return <SignInFirst />;
  const start = async (t: string) => {
    setErr("");
    try { const r = await api.post<{ run_id: string }>("/api/agent/runs", { ticket_id: t, prompt }); window.history.replaceState(null, "", `#/agent/run/${r.run_id}`); setRunId(r.run_id); }
    catch (e: any) { setErr(e.message); }
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[330px_1fr] gap-4">
        <div className="space-y-3">
          <Card className="p-4">
            <div className="text-[13.5px] font-semibold">My KYC exceptions</div>
            <div className="text-[12px] text-ink-2">As <b>{st?.person?.name}</b>. The agent works one exception to an outcome in CaseFlow Classic.</div>
            <div className="mt-3 space-y-1.5" data-testid="my-exceptions">
              {mine.map((t) => (
                <div key={t.ticket_id} className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${t.last_run?.id === runId ? "border-navy" : "border-black/[0.06]"}`}>
                  <div className="min-w-0 flex-1">
                    <div className="text-[12.5px] font-semibold">{t.ticket_id} <span className="font-normal text-ink-2">· {KIND[t.kind] ?? t.kind}</span></div>
                    <div className="truncate text-[11px] text-ink-3">{t.title}</div>
                    {t.last_run && <div className="mt-0.5"><StatusChip status={t.last_run.status} /></div>}
                  </div>
                  <Button testId={`run-${t.ticket_id}`} variant="secondary" onClick={() => start(t.ticket_id)}><Play size={12} /> Run</Button>
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-center gap-2 text-[12px]">
              <span className="text-ink-2">Prompt</span>
              <select data-testid="agent-prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} className="h-8 rounded-lg border border-black/10 px-2 text-[12px]">
                {(st?.prompts ?? ["ops_v1"]).map((p) => <option key={p}>{p}</option>)}
              </select>
            </div>
            {err && <div className="mt-2 rounded-lg bg-ember-50 px-3 py-2 text-[12px]">{err}</div>}
          </Card>
          <Card className="p-4" testId="agent-tickets">
            <div className="text-[12px] font-semibold uppercase tracking-wide text-ink-3">Today's tickets</div>
            <div className="mt-2"><TicketChips st={st} /></div>
            {st && <div className="mt-3 text-[11.5px] text-ink-2" data-testid="agent-limits">Limits on one run: {st.limits.max_steps} steps · {st.limits.max_tokens.toLocaleString()} tokens · {st.limits.max_seconds} s · the same action at most {st.limits.max_repeats - 1} times in a row</div>}
          </Card>
        </div>
        {runId ? <RunView key={runId} runId={runId} onEnd={() => setRefresh((x) => x + 1)} /> :
          <Card className="p-5 text-[12.5px] text-ink-3">Press Run on an exception. Each step shows what the agent thought, the tool it called, and what the gate decided. Click a step to see CaseFlow Classic as the agent saw it.</Card>}
      </div>
      <CaseflowCard refresh={refresh} />
    </div>
  );
}
