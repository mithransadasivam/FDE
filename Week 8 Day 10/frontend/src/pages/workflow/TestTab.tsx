// Crash test (homework): twenty case workflows, one crash armed in each, every case scored from the bank's own records.
import { useEffect, useState } from "react";
import { api, type CrashTest } from "../../api";
import { Card, Chip, Kpi } from "../../components/ui";

const CHECKS = ["end", "messages", "caseflow", "escalation", "agent_once"];

export default function TestTab() {
  const [t, setT] = useState<CrashTest | null>(null);
  useEffect(() => { const load = () => api.get<CrashTest>("/api/workflow/crashtest").then(setT); load(); const x = setInterval(load, 3000); return () => clearInterval(x); }, []);
  if (!t) return null;
  return (
    <div className="space-y-4">
      <Card className="p-4" testId="crashtest-how">
        <div className="text-[13.5px] font-semibold">Run it from backend/, with npm run dev running</div>
        <div className="mt-1 font-mono text-[12.5px]">python -m scripts.run_crashes</div>
        <div className="mt-1 text-[12px] text-ink-2">20 exceptions as Helen Achebe, one crash armed in each (data/Day10_HW_Slide04_crash_plan.json). The script decides each approval and makes each applicant reply as the plan says. About 5 minutes with 20-second days.</div>
      </Card>
      {t.at ? (
        <div className="grid grid-cols-[1fr_260px] gap-4">
          <Card className="overflow-hidden" testId="crashtest-table">
            <table className="w-full text-left text-[11.5px]">
              <thead className="bg-mist text-[10px] uppercase tracking-wide text-ink-3"><tr><th className="px-3 py-1.5">Case</th><th>Crash</th><th>End</th><th>Writes (req · rem · esc · out · com)</th>{CHECKS.map((c) => <th key={c} className="text-center">{c.replace("_", " ")}</th>)}</tr></thead>
              <tbody>{t.results.map((r) => (
                <tr key={r.id} data-testid={`crash-row-${r.id}`} className={`border-t border-black/[0.05] ${r.score.passed === false ? "bg-ember-50/50" : ""}`}>
                  <td className="px-3 py-1 font-mono">{r.id} {r.ticket_id}</td>
                  <td className="font-mono">{r.crash}{r.crash !== "none" && <span className={r.crashes.length ? "text-teal" : "text-amber"}> {r.crashes.length ? "fired" : "did not fire"}</span>}</td>
                  <td>{r.end || "not ended"}</td>
                  <td className="font-mono">{r.counts.requests}·{r.counts.reminders}·{r.counts.escalations}·{r.counts.caseflow_outcomes}·{r.counts.outcome_comments}
                    <span className="text-ink-3"> / {r.expected.requests}·{r.expected.reminders}·{r.expected.escalations}·{r.expected.caseflow_outcomes}·{r.expected.outcome_comments}</span></td>
                  {CHECKS.map((c) => <td key={c} className="text-center">{r.score.passed === null ? "–" : r.score.checks[c] ? <span className="text-teal">✓</span> : <span className="font-bold text-ember">✗</span>}</td>)}
                </tr>))}</tbody>
            </table>
          </Card>
          <div className="space-y-3" data-testid="crashtest-summary">
            <Kpi label="Cases passed" value={t.scored ? `${t.passed} of ${t.total}` : "not scored"} tone={t.scored && t.passed === t.total ? "teal" : "amber"} sub={t.scored ? `run at ${t.at?.slice(11)}` : "score_case() is not built (Task 1)"} />
            <Kpi label="Crashes that fired" value={t.crashes_fired ?? 0} sub={`one day = ${t.day_seconds} s · ${t.seconds} s in all`} />
            <Card className="p-3 text-[11.5px] text-ink-2">Counts are the bank's: <Chip>req</Chip> requests, <Chip>rem</Chip> reminders, <Chip>esc</Chip> escalation comments, <Chip>out</Chip> CaseFlow outcomes, <Chip>com</Chip> “Outcome recorded” comments. Got / expected.</Card>
          </div>
        </div>
      ) : <Card className="p-4 text-[12.5px] text-ink-3" testId="crashtest-empty">No crash test yet.</Card>}
    </div>
  );
}
