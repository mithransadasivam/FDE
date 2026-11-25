// Model lab (Day 11): a small model the bank runs itself, taught by the pilot's own reads. It reads the documents it is
// sure of; the pilot (Sonnet 5, ADR-003) reads the rest. Every score is against Tom's keyed labels, never the teacher.
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import CascadeTab from "./modellab/CascadeTab";
import DriftTab from "./modellab/DriftTab";
import ReadTab from "./modellab/ReadTab";
import ScaleTab from "./modellab/ScaleTab";
import TrainTab from "./modellab/TrainTab";

const TABS = [
  { id: "train", label: "Teacher and student", hint: "Train on the pilot's reads" },
  { id: "read", label: "Read a document", hint: "Four fields, and how sure" },
  { id: "cascade", label: "Cascade", hint: "Small model first, pilot for the rest" },
  { id: "scale", label: "Client scale", hint: "The month at the bank's volumes" },
  { id: "drift", label: "New document type", hint: "Council tax bills (homework)" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "train") as TabId;

export default function ModelLab() {
  const [tab, setTab] = useState<TabId>(fromHash());
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/modellab/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">Client workspace <ChevronRight size={13} /> <span className="text-ink-2">Model lab</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Model lab: a small model for the bank's documents, taught by the pilot</h1>
      <nav className="mt-4 grid grid-cols-5 gap-2">
        {TABS.map((t, i) => {
          const on = t.id === tab;
          return (
            <button key={t.id} data-testid={`mtab-${t.id}`} onClick={() => go(t.id)}
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
        {tab === "train" && <TrainTab />}
        {tab === "read" && <ReadTab />}
        {tab === "cascade" && <CascadeTab />}
        {tab === "scale" && <ScaleTab />}
        {tab === "drift" && <DriftTab />}
      </div>
    </div>
  );
}
