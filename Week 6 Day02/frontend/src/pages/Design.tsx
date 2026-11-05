// Design & cost: from findings to a justified architecture, a run-cost and a delivery plan.
import { ChevronRight } from "lucide-react";
import { useState, useEffect } from "react";
import AdrTab from "./design/AdrTab";
import ArchitectureTab from "./design/ArchitectureTab";
import CostTab from "./design/CostTab";
import PlanTab from "./design/PlanTab";
import ReadinessTab from "./design/ReadinessTab";

const TABS = [
  { id: "data", label: "Data readiness", hint: "Can we use the data?" },
  { id: "architecture", label: "Architectures", hint: "Which design meets the rules?" },
  { id: "cost", label: "Run-cost", hint: "What will it cost each month?" },
  { id: "adr", label: "Decision record", hint: "What we chose, and why" },
  { id: "plan", label: "Delivery plan", hint: "How we get to production" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "data") as TabId;

export default function Design() {
  const [tab, setTab] = useState<TabId>(fromHash());
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/design/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1360px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">FDE control room <ChevronRight size={13} /> <span className="text-ink-2">Design &amp; cost</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Solution design: UC1 proof-of-address check</h1>
      <nav className="mt-4 grid grid-cols-5 gap-2">
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
        {tab === "data" && <ReadinessTab />}
        {tab === "architecture" && <ArchitectureTab />}
        {tab === "cost" && <CostTab />}
        {tab === "adr" && <AdrTab />}
        {tab === "plan" && <PlanTab />}
      </div>
    </div>
  );
}
