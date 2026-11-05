// Discovery: from a vague request to findings, success criteria and a first use case.
import { ChevronRight, FileDown } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Criterion, type Finding, type Question, type UseCase } from "../api";
import { Button } from "../components/ui";
import BriefTab from "./discovery/BriefTab";
import FindingsTab from "./discovery/FindingsTab";
import NotesTab from "./discovery/NotesTab";
import QuestionsTab from "./discovery/QuestionsTab";
import SuccessTab from "./discovery/SuccessTab";

const TABS = [
  { id: "brief", label: "Brief", hint: "What we were told" },
  { id: "questions", label: "Question plan", hint: "What we will ask" },
  { id: "notes", label: "Interview notes", hint: "What we heard" },
  { id: "findings", label: "Findings", hint: "What it means" },
  { id: "success", label: "Success & scope", hint: "What we will build first" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function tabFromHash(): TabId {
  const t = window.location.hash.split("/")[2];
  return (TABS.find((x) => x.id === t)?.id ?? "brief") as TabId;
}

export default function Discovery() {
  const [tab, setTab] = useState<TabId>(tabFromHash());
  const [counts, setCounts] = useState<Record<string, string>>({});
  const [toast, setToast] = useState("");

  const refreshCounts = useCallback(async () => {
    const [qs, notes, fs, cs, us] = await Promise.all([
      api.get<Question[]>("/api/questions"),
      api.get<{ text: string }>("/api/notes"),
      api.get<Finding[]>("/api/findings"),
      api.get<Criterion[]>("/api/criteria").catch(() => [] as Criterion[]),
      api.get<UseCase[]>("/api/usecases"),
    ]);
    const words = notes.text.split(/\s+/).filter(Boolean).length;
    setCounts({
      brief: "read",
      questions: qs.length ? `${qs.filter((q) => q.starred).length} of ${qs.length} starred` : "not drafted",
      notes: words ? `${words} words` : "empty",
      findings: fs.length ? `${fs.length} findings` : "not extracted",
      success: `${cs.filter((c) => c.problems.length === 0).length}/${cs.length} measurable${us.some((u) => u.first_choice) ? " · scoped" : ""}`,
    });
  }, []);

  useEffect(() => { refreshCounts(); }, [refreshCounts, tab]);
  useEffect(() => {
    const on = () => setTab(tabFromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const go = (t: TabId) => { window.location.hash = `#/discovery/${t}`; setTab(t); };
  const exportSummary = async () => {
    const r = await api.post<{ path: string }>("/api/summary/export");
    setToast(`Saved ${r.path}`);
    setTimeout(() => setToast(""), 3500);
  };

  return (
    <div className="mx-auto max-w-[1360px]">
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">FDE control room <ChevronRight size={13} /> <span className="text-ink-2">Discovery</span></div>
          <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Discovery: Kestrelmoor Bank</h1>
        </div>
        <div className="flex items-center gap-3">
          {toast && <span data-testid="toast" className="rounded-lg bg-teal-50 px-3 py-2 text-[12.5px] font-medium text-teal">{toast}</span>}
          <Button variant="secondary" onClick={exportSummary} testId="export-summary"><FileDown size={14} /> Export summary</Button>
        </div>
      </div>

      <nav className="mt-4 grid grid-cols-5 gap-2">
        {TABS.map((t, i) => {
          const on = t.id === tab;
          return (
            <button key={t.id} data-testid={`tab-${t.id}`} onClick={() => go(t.id)}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${on ? "border-navy bg-navy text-white" : "border-black/[0.06] bg-white hover:border-black/20"}`}>
              <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-[12px] font-bold ${on ? "bg-ember text-white" : "bg-mist text-ink-2"}`}>{i + 1}</span>
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold">{t.label}</span>
                <span className={`block truncate text-[11.5px] ${on ? "text-white/60" : "text-ink-3"}`}>{counts[t.id] ?? t.hint}</span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="mt-4">
        {tab === "brief" && <BriefTab />}
        {tab === "questions" && <QuestionsTab onChange={refreshCounts} />}
        {tab === "notes" && <NotesTab onChange={refreshCounts} />}
        {tab === "findings" && <FindingsTab onChange={refreshCounts} />}
        {tab === "success" && <SuccessTab onChange={refreshCounts} />}
      </div>
    </div>
  );
}
