// Pipeline: the October batch read at scale (Day 6). Parse every document, compare two ways of reading it,
// route doubtful fields to the KYC analysts, and run the whole set as a batch.
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type PipelineStatus } from "../api";
import { useDocSet } from "./pipeline/useDocSet";
import BatchTab from "./pipeline/BatchTab";
import CompareTab from "./pipeline/CompareTab";
import ParseTab from "./pipeline/ParseTab";
import RoutingTab from "./pipeline/RoutingTab";

const TABS = [
  { id: "parse", label: "Parse", hint: "What did the bank send?" },
  { id: "compare", label: "Compare", hint: "Which method reads better?" },
  { id: "routing", label: "Routing", hint: "Which fields need a person?" },
  { id: "batch", label: "Batch", hint: "Can it run the month?" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "parse") as TabId;

export default function Pipeline() {
  const [tab, setTab] = useState<TabId>(fromHash());
  const [set, setSet] = useDocSet();
  const [sets, setSets] = useState<PipelineStatus["sets"]>([]);
  useEffect(() => { api.get<PipelineStatus>("/api/pipeline/status").then((s) => { setSets(s.sets); if (!s.sets.some((x) => x.name === set)) setSet("october"); }); }, []);
  const label = sets.find((s) => s.name === set)?.label ?? "";
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/pipeline/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">FDE control room <ChevronRight size={13} /> <span className="text-ink-2">Pipeline</span></div>
      <div className="mt-1 flex items-end justify-between gap-4">
        <h1 className="text-[24px] font-semibold tracking-tight">Pipeline: {label || "the October batch"}</h1>
        {sets.length > 1 && (
          <label className="text-[11.5px] font-semibold text-ink-3">Document set
            <select data-testid="doc-set" value={set} onChange={(e) => setSet(e.target.value)} className="mt-1 block rounded-lg border border-black/10 bg-white px-2 py-1.5 text-[12.5px]">
              {sets.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
          </label>
        )}
      </div>
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
        {tab === "parse" && <ParseTab key={set} set={set} />}
        {tab === "compare" && <CompareTab key={set} set={set} />}
        {tab === "routing" && <RoutingTab key={set} set={set} />}
        {tab === "batch" && <BatchTab key={set} set={set} />}
      </div>
    </div>
  );
}
