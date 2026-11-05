import { Loader2, Sparkles, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Area, type Question } from "../../api";
import { Button, Card } from "../../components/ui";

const AREAS: { id: Area; label: string; tone: string }[] = [
  { id: "goals", label: "Goals", tone: "bg-navy" },
  { id: "process", label: "Process", tone: "bg-teal" },
  { id: "data", label: "Data & systems", tone: "bg-[#5B6BBF]" },
  { id: "risk", label: "Risk & approvals", tone: "bg-ember" },
  { id: "success", label: "Success", tone: "bg-amber" },
];
const TARGET = 8;

export default function QuestionsTab({ onChange }: { onChange: () => void }) {
  const [qs, setQs] = useState<Question[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api.get<Question[]>("/api/questions").then(setQs); }, []);

  const draft = async () => {
    setBusy(true); setError("");
    try { setQs(await api.post<Question[]>("/api/questions/draft")); onChange(); }
    catch (e) { setError(String((e as Error).message)); }
    finally { setBusy(false); }
  };
  const star = async (q: Question) => {
    const u = await api.put<Question>(`/api/questions/${q.id}`, { starred: !q.starred });
    setQs((all) => all.map((x) => (x.id === u.id ? u : x))); onChange();
  };
  const starred = qs.filter((q) => q.starred).length;

  return (
    <div>
      <Card className="flex items-center justify-between px-4 py-3">
        <div>
          <div className="text-[14px] font-semibold">Question plan for the discovery session</div>
          <div className="text-[12.5px] text-ink-2">Claude drafts questions from the brief. You choose the {TARGET} you will ask first: star them.</div>
        </div>
        <div className="flex items-center gap-3">
          {qs.length > 0 && (
            <span data-testid="starred-count" className={`rounded-lg px-3 py-1.5 text-[12.5px] font-semibold ${starred === TARGET ? "bg-teal-50 text-teal" : "bg-mist text-ink-2"}`}>
              {starred} / {TARGET} starred
            </span>
          )}
          <Button onClick={draft} disabled={busy} testId="draft-questions">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} {qs.length ? "Redraft" : "Draft question plan"}
          </Button>
        </div>
      </Card>
      {error && <div className="mt-3 rounded-lg bg-ember-50 px-4 py-2 text-[12.5px] text-ember">{error}</div>}
      <div className="mt-4 grid grid-cols-5 gap-3">
        {AREAS.map((a) => {
          const list = qs.filter((q) => q.area === a.id);
          return (
            <div key={a.id} data-testid={`area-${a.id}`}>
              <div className="mb-2 flex items-center gap-2 px-1">
                <span className={`h-2.5 w-2.5 rounded-full ${a.tone}`} />
                <span className="text-[12.5px] font-semibold">{a.label}</span>
                <span className="text-[12px] text-ink-3">{list.length}</span>
              </div>
              <div className="space-y-2">
                {list.map((q) => (
                  <Card key={q.id} testId={`question-${q.id}`} className={`p-3 ${q.starred ? "ring-2 ring-amber" : ""}`}>
                    <div className="flex items-start gap-2">
                      <div className="flex-1 text-[12.5px] font-medium leading-snug">{q.text}</div>
                      <button aria-label="star" onClick={() => star(q)} className="mt-0.5 text-ink-3 hover:text-amber">
                        <Star size={15} className={q.starred ? "fill-amber text-amber" : ""} />
                      </button>
                    </div>
                    <div className="mt-1.5 text-[11.5px] leading-snug text-ink-3">{q.why}</div>
                  </Card>
                ))}
                {!list.length && <div className="rounded-xl border border-dashed border-black/10 p-4 text-center text-[12px] text-ink-3">No questions yet</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
