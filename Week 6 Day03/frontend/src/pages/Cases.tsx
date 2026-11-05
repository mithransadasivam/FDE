// Cases: the first client screen (UC1 prototype), plus the FDE's demo and PR review views.
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import CaseReview from "./cases/CaseReview";
import DemoTab from "./cases/DemoTab";
import PrReviewTab from "./cases/PrReviewTab";
import QueueTab from "./cases/QueueTab";

type View = { tab: "queue" | "case" | "demo" | "pr"; id?: string };
const fromHash = (): View => {
  const [, , tab, id] = window.location.hash.split("/");
  if (tab === "case" && id) return { tab: "case", id };
  if (tab === "demo" || tab === "pr") return { tab };
  return { tab: "queue" };
};

const TABS = [
  { id: "queue", label: "Queue", who: "Analyst" },
  { id: "demo", label: "Demo vs success criteria", who: "FDE" },
  { id: "pr", label: "PR review", who: "FDE" },
] as const;

export default function Cases() {
  const [view, setView] = useState<View>(fromHash());
  useEffect(() => {
    const on = () => setView(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (h: string) => { window.location.hash = h; setView(fromHash()); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">
        Client workspace <ChevronRight size={13} />
        <button className="text-ink-2 hover:underline" onClick={() => go("#/cases/queue")}>Cases</button>
        {view.tab === "case" && <><ChevronRight size={13} /><span className="text-ink-2">{view.id}</span></>}
        <span className="ml-2 rounded-md bg-amber-50 px-1.5 py-0.5 text-[10.5px] font-semibold text-amber">Prototype · fictional documents</span>
      </div>
      <div className="mt-1 flex items-end justify-between">
        <h1 className="text-[24px] font-semibold tracking-tight">Proof-of-address check</h1>
        <nav className="flex gap-1 rounded-xl bg-white p-1 shadow-[0_1px_2px_rgba(27,31,59,0.06)]">
          {TABS.map((t) => {
            const on = t.id === view.tab || (t.id === "queue" && view.tab === "case");
            return (
              <button key={t.id} data-testid={`ctab-${t.id}`} onClick={() => go(`#/cases/${t.id}`)}
                className={`rounded-lg px-3 py-1.5 text-[12.5px] font-semibold ${on ? "bg-navy text-white" : "text-ink-2 hover:bg-mist"}`}>
                {t.label} <span className={`ml-1 text-[10px] font-medium ${on ? "text-white/50" : "text-ink-3"}`}>{t.who}</span>
              </button>
            );
          })}
        </nav>
      </div>
      <div className="mt-4">
        {view.tab === "queue" && <QueueTab open={(id) => go(`#/cases/case/${id}`)} />}
        {view.tab === "case" && view.id && <CaseReview key={view.id} caseId={view.id} back={() => go("#/cases/queue")} />}
        {view.tab === "demo" && <DemoTab />}
        {view.tab === "pr" && <PrReviewTab />}
      </div>
    </div>
  );
}
