// One case, for days: start a case workflow for one of my exceptions, and follow it on the case's clock.
import { Loader2, PlayCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type CaseRow, type WfException } from "../../api";
import { Button, Card } from "../../components/ui";
import { SignInFirst } from "../agent/RunTab";
import { CaseView, StateChip, TicketChips10, WorkerBar, useWorkflowStatus } from "./parts";

const KIND: Record<string, string> = { overdue: "Overdue", applicant_follow_up: "Applicant follow-up", escalation: "Escalation" };

export default function CaseTab() {
  const st = useWorkflowStatus();
  const [mine, setMine] = useState<WfException[]>([]);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [open, setOpen] = useState<string | null>(window.location.hash.split("/")[3] || null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const load = async () => {
    setCases((await api.get<{ cases: CaseRow[] }>("/api/workflow/cases")).cases);
    try { setMine((await api.get<{ tickets: WfException[] }>("/api/workflow/exceptions")).tickets); } catch { setMine([]); }
  };
  useEffect(() => { load(); const t = setInterval(load, 2000); return () => clearInterval(t); }, []);
  useEffect(() => {
    const on = () => setOpen(window.location.hash.split("/")[3] || null);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  if (st && !st.person) return <SignInFirst />;
  const start = async (t: string) => {
    setBusy(t); setErr("");
    try {
      const r = await api.post<{ key: string }>("/api/workflow/cases", { ticket_id: t });
      window.history.replaceState(null, "", `#/workflows/case/${r.key}`);
      setOpen(r.key); await load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(""); }
  };
  const pick = (k: string) => { window.history.replaceState(null, "", `#/workflows/case/${k}`); setOpen(k); };
  return (
    <div className="space-y-4">
      <WorkerBar st={st} />
      <div className="grid grid-cols-[340px_1fr] gap-4">
        <div className="space-y-3">
          <Card className="p-4" testId="wf-exceptions">
            <div className="text-[13px] font-semibold">My open exceptions</div>
            <div className="mb-2 text-[11.5px] text-ink-2">Start a case: you delegate it to the workflow, which acts for you for up to 14 days.</div>
            {mine.map((t) => (
              <div key={t.ticket_id} className="flex items-center gap-2 border-t border-black/[0.05] py-2">
                <div className="flex-1"><div className="font-mono text-[12.5px] font-semibold">{t.ticket_id}</div><div className="text-[11px] text-ink-3">{KIND[t.kind] ?? t.kind}</div></div>
                <Button testId={`start-${t.ticket_id}`} onClick={() => start(t.ticket_id)} disabled={!!busy || !!t.active}>
                  {busy === t.ticket_id ? <Loader2 size={13} className="animate-spin" /> : <PlayCircle size={13} />} {t.active ? "Running" : "Start case"}</Button>
              </div>
            ))}
            {err && <div className="mt-2 rounded-lg bg-ember-50 px-3 py-2 text-[12px]" data-testid="wf-error">{err}</div>}
          </Card>
          <Card className="overflow-hidden" testId="wf-cases">
            <div className="px-4 py-2 text-[13px] font-semibold">Case workflows</div>
            {cases.map((c) => (
              <button key={c.key} data-testid={`case-${c.key}`} onClick={() => pick(c.key)}
                className={`block w-full border-t border-black/[0.05] px-4 py-2 text-left ${open === c.key ? "bg-teal-50/70" : "hover:bg-mist/60"}`}>
                <div className="flex items-center gap-2"><span className="font-mono text-[12px] font-semibold">{c.ticket_id}</span><StateChip state={c.state} />
                  <span className="ml-auto text-[11px] text-ink-3">day {c.day.toFixed(1)}</span></div>
                <div className="mt-0.5 truncate text-[11px] text-ink-2">{c.last}</div>
              </button>
            ))}
            {!cases.length && <div className="border-t border-black/[0.05] px-4 py-3 text-[12px] text-ink-3">No case workflow yet.</div>}
          </Card>
          <Card className="p-4"><div className="mb-2 text-[12px] font-semibold">Today's tickets</div><TicketChips10 st={st} /></Card>
        </div>
        <div>{open ? <CaseView key={open} caseKey={open} policy={st?.policy} /> :
          <Card className="p-6 text-[13px] text-ink-2" testId="wf-empty">Start a case on the left. The agent works it as you; you approve the outcome; the workflow records it, chases the applicant on the playbook's clock ({st?.policy.reminder_after_days ?? 3} days, then {st?.policy.escalate_after_days ?? 7}), and works the case again when the documents arrive.</Card>}</div>
      </div>
    </div>
  );
}
