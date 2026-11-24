// Workflows: a KYC case kept going for days by a durable workflow (Day 10). The agent proposes, the person decides,
// the workflow writes, chases the applicant on the playbook's clock, and carries on after any crash.
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import CaseTab from "./workflow/CaseTab";
import CrashTab from "./workflow/CrashTab";
import QueueTab10 from "./workflow/QueueTab10";
import TestTab from "./workflow/TestTab";

const TABS = [
  { id: "case", label: "One case, for days", hint: "Propose, wait, write, chase" },
  { id: "crash", label: "Crashes and writes", hint: "What happens when the worker dies?" },
  { id: "queue", label: "My queue", hint: "Four cases, start to end" },
  { id: "test", label: "Crash test", hint: "Twenty cases, one crash each (homework)" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "case") as TabId;

export default function Workflows() {
  const [tab, setTab] = useState<TabId>(fromHash());
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/workflows/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">Client workspace <ChevronRight size={13} /> <span className="text-ink-2">Workflows</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Workflows: KYC cases that wait days, and survive a crash</h1>
      <nav className="mt-4 grid grid-cols-4 gap-2">
        {TABS.map((t, i) => {
          const on = t.id === tab;
          return (
            <button key={t.id} data-testid={`wtab-${t.id}`} onClick={() => go(t.id)}
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
        {tab === "case" && <CaseTab />}
        {tab === "crash" && <CrashTab />}
        {tab === "queue" && <QueueTab10 />}
        {tab === "test" && <TestTab />}
      </div>
    </div>
  );
}
