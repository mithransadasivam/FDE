// Data agent: the FDE's view of Ask the data (Day 7). What the warehouse holds and what the model is told,
// the safety checks, row security for the three roles, and the evaluation on the bank's business questions.
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import EvalTab from "./data/EvalTab";
import RowSecurityTab from "./data/RowSecurityTab";
import SafetyTab from "./data/SafetyTab";
import WarehouseTab from "./data/WarehouseTab";

const TABS = [
  { id: "warehouse", label: "Warehouse", hint: "What the model is told" },
  { id: "safety", label: "Safety", hint: "Can a query do harm?" },
  { id: "rows", label: "Row security", hint: "Who sees which rows?" },
  { id: "eval", label: "Evaluation", hint: "Are the answers right?" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "warehouse") as TabId;

export default function DataAgent() {
  const [tab, setTab] = useState<TabId>(fromHash());
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/data/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">FDE control room <ChevronRight size={13} /> <span className="text-ink-2">Data agent</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Data agent: questions over CaseFlow</h1>
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
        {tab === "warehouse" && <WarehouseTab />}
        {tab === "safety" && <SafetyTab />}
        {tab === "rows" && <RowSecurityTab />}
        {tab === "eval" && <EvalTab />}
      </div>
    </div>
  );
}
