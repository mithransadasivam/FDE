// Agent runs: the operations agent works KYC exceptions in CaseFlow Classic, as the signed-in person (Day 9).
// One run step by step, the approvals it asks for, Tom's morning queue, and the 20-case evaluation (homework).
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import ApprovalsTab from "./agent/ApprovalsTab";
import EvalTab from "./agent/EvalTab";
import QueueTab from "./agent/QueueTab";
import RunTab from "./agent/RunTab";

const TABS = [
  { id: "run", label: "Work one exception", hint: "What does the agent do?" },
  { id: "approvals", label: "Approvals", hint: "Who says yes to a write?" },
  { id: "queue", label: "My queue", hint: "Four exceptions, start to end" },
  { id: "eval", label: "Evaluation", hint: "Twenty runs, scored (homework)" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "run") as TabId;

export default function AgentRuns() {
  const [tab, setTab] = useState<TabId>(fromHash());
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/agent/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">FDE control room <ChevronRight size={13} /> <span className="text-ink-2">Agent runs</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Agent runs: the operations agent in CaseFlow Classic</h1>
      <nav className="mt-4 grid grid-cols-4 gap-2">
        {TABS.map((t, i) => {
          const on = t.id === tab;
          return (
            <button key={t.id} data-testid={`dtab-${t.id}`} onClick={() => go(t.id)}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${on ? "border-navy bg-navy text-white" : "border-black/[0.06] bg-white hover:border-black/20"}`}>
              <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-[12px] font-bold ${on ? "bg-ember text-white" : "bg-mist text-ink-2"}`}>{i + 1}</span>
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold">{t.label}</span>
                <span className={`block truncate text-[11.5px] ${on ? "text-white/60" : "text-ink-3"}`}>{t.hint}</span>
              </span>
            </button>
          );
        })}
      </nav>
      <div className="mt-4">
        {tab === "run" && <RunTab />}
        {tab === "approvals" && <ApprovalsTab />}
        {tab === "queue" && <QueueTab />}
        {tab === "eval" && <EvalTab />}
      </div>
    </div>
  );
}
