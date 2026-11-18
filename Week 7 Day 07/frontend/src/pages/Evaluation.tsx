// Evaluation: does the prototype meet the client's definition of quality? Built with Tom, the domain expert.
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import CompareTab from "./evaluation/CompareTab";
import ErrorsTab from "./evaluation/ErrorsTab";
import JudgesTab from "./evaluation/JudgesTab";
import LabellingTab from "./evaluation/LabellingTab";

const TABS = [
  { id: "errors", label: "Error analysis", hint: "What goes wrong, and how often?" },
  { id: "labelling", label: "Labelling with Tom", hint: "Do we agree on what is right?" },
  { id: "judges", label: "LLM judges", hint: "Can a model check it for us?" },
  { id: "compare", label: "Before and after", hint: "Did the fix work?" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "errors") as TabId;

export default function Evaluation() {
  const [tab, setTab] = useState<TabId>(fromHash());
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/evaluation/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">FDE control room <ChevronRight size={13} /> <span className="text-ink-2">Evaluation</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Evaluation: UC1 against Tom's definition of right</h1>
      <nav className="mt-4 grid grid-cols-4 gap-2">
        {TABS.map((t, i) => {
          const on = t.id === tab;
          return (
            <button key={t.id} data-testid={`etab-${t.id}`} onClick={() => go(t.id)}
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
        {tab === "errors" && <ErrorsTab />}
        {tab === "labelling" && <LabellingTab />}
        {tab === "judges" && <JudgesTab />}
        {tab === "compare" && <CompareTab />}
      </div>
    </div>
  );
}
