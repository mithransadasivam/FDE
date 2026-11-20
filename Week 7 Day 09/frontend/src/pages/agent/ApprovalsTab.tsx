// Approvals: every write to a system of record waits for the person the agent works for. The bank's risk table says which.
import { useEffect, useState } from "react";
import { api, type Approval9, type AgentStatus } from "../../api";
import { Card, Chip } from "../../components/ui";
import { ApprovalCard } from "./parts";
import { useAgentStatus } from "./RunTab";

const TIER = { read: "teal", log: "teal", approve: "amber", deny: "ember" } as const;

export function RiskTable({ st }: { st: AgentStatus | null }) {
  return (
    <Card className="overflow-hidden" testId="risk-table">
      <div className="px-4 py-3">
        <div className="text-[13.5px] font-semibold">The bank's risk table: what the gate does with each action</div>
        <div className="text-[12px] text-ink-2">data/Day09_Slide21_action_risks.csv · anything not in the table is refused</div>
      </div>
      <table className="w-full text-left text-[12px]">
        <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">System</th><th>Action</th><th>Tier</th><th>Why</th></tr></thead>
        <tbody>{(st?.rules ?? []).map((r, i) => (
          <tr key={i} className="border-t border-black/[0.05]"><td className="px-4 py-1">{r.system}</td><td className="font-mono text-[11.5px]">{r.tool} {r.target !== "*" && `"${r.target}"`}</td>
            <td><Chip tone={TIER[r.tier]}>{r.tier}</Chip></td><td className="pr-4 text-ink-2">{r.why}</td></tr>))}</tbody>
      </table>
    </Card>
  );
}

export default function ApprovalsTab() {
  const st = useAgentStatus();
  const [ap, setAp] = useState<{ pending: Approval9[]; recent: Approval9[] }>({ pending: [], recent: [] });
  const load = () => api.get<{ pending: Approval9[]; recent: Approval9[] }>("/api/agent/approvals").then(setAp);
  useEffect(() => { load(); const t = setInterval(load, 1500); return () => clearInterval(t); }, []);
  return (
    <div className="space-y-4">
      <div className="space-y-3" data-testid="approvals-pending">
        {ap.pending.map((a) => <ApprovalCard key={a.id} a={a} onDone={load} />)}
        {!ap.pending.length && <Card className="p-4 text-[12.5px] text-ink-3">Nothing waits for you. When a run reaches a write, its approval appears here and in the run.</Card>}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Card className="overflow-hidden" testId="approvals-recent">
          <div className="px-4 py-3 text-[13.5px] font-semibold">Decided</div>
          <table className="w-full text-left text-[12px]">
            <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Exception</th><th>What</th><th>Decision</th></tr></thead>
            <tbody>{ap.recent.map((a) => (
              <tr key={a.id} className="border-t border-black/[0.05] align-top"><td className="px-4 py-1.5 font-mono text-[11.5px]">{a.ticket_id}</td>
                <td className="py-1.5">{a.shows.find((r) => r[0] === "Outcome")?.[1] ?? a.target}</td>
                <td className="py-1.5 pr-4"><Chip tone={a.status === "approved" ? "teal" : "ember"}>{a.status}</Chip> <span className="text-ink-2">{a.decided_by}{a.note && `: ${a.note}`}</span></td></tr>))}</tbody>
          </table>
        </Card>
        <RiskTable st={st} />
      </div>
    </div>
  );
}
