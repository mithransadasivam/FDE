import { ArrowRight, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type QueueRow } from "../../api";
import { Card, Chip, Kpi } from "../../components/ui";

const STATE = {
  ready: { tone: "teal", text: "Ready to approve" },
  look: { tone: "amber", text: "Needs a look" },
  fails: { tone: "ember", text: "Fails a rule" },
  new: { tone: "mist", text: "Not read yet" },
  not_built: { tone: "mist", text: "Ticket not built" },
} as const;
const DECIDED = { approve: "Approved", ask_applicant: "Asked applicant", escalate: "Escalated" } as Record<string, string>;

export default function QueueTab({ open }: { open: (id: string) => void }) {
  const [rows, setRows] = useState<QueueRow[] | null>(null);
  useEffect(() => { api.get<QueueRow[]>("/api/cases").then(setRows); }, []);
  if (!rows) return <div className="flex items-center gap-2 text-[13px] text-ink-2"><Loader2 size={14} className="animate-spin" /> Reading the queue…</div>;
  const count = (s: string) => rows.filter((r) => r.state === s && !r.decision).length;
  return (
    <div>
      <div className="grid grid-cols-4 gap-3">
        <Kpi label="Waiting for a decision" value={rows.filter((r) => !r.decision).length} sub={`${rows.length} proof-of-address documents`} />
        <Kpi label="Ready to approve" value={count("ready")} tone="teal" sub="every field sure, every rule passed" />
        <Kpi label="Needs a look" value={count("look")} tone="amber" sub="a field a person must confirm" />
        <Kpi label="Fails a rule" value={count("fails")} tone="ember" sub="ask the applicant, or escalate" />
      </div>
      <Card className="mt-4 overflow-hidden">
        <table className="w-full text-[13px]" data-testid="queue">
          <thead className="bg-mist text-left text-[11px] uppercase tracking-wide text-ink-3">
            <tr><th className="px-4 py-2.5">Case</th><th>Applicant</th><th>Issuer</th><th>Received</th><th>Channel</th><th>Prototype says</th><th>Decision</th><th /></tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const st = STATE[r.state];
              return (
                <tr key={r.case_id} data-testid={`row-${r.case_id}`} onClick={() => open(r.case_id)} className="cursor-pointer border-t border-black/[0.05] hover:bg-mist/60">
                  <td className="px-4 py-2 font-mono text-[12px] text-ink-2">{r.case_id}</td>
                  <td className="font-semibold">{r.applicant_name}</td>
                  <td className="text-ink-2">{r.issuer || "—"}</td>
                  <td className="tabular-nums text-ink-2">{r.received_date}</td>
                  <td className="text-ink-2">{r.channel}</td>
                  <td><Chip tone={st.tone}>{st.text}{r.state === "look" && r.doubtful ? ` · ${r.doubtful} field` : ""}</Chip></td>
                  <td>{r.decision ? <Chip tone="navy">{DECIDED[r.decision] ?? r.decision}</Chip> : <span className="text-ink-3">—</span>}</td>
                  <td className="pr-4 text-right text-ink-3"><ArrowRight size={14} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
