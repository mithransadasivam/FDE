import { AlertTriangle, CheckCircle2, FileText, Loader2, ScanSearch, ThumbsDown, ThumbsUp } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Finding, type FindingKind } from "../../api";
import PainMatrix from "../../components/PainMatrix";
import { Button, Card, Chip, Kpi, NotBuilt } from "../../components/ui";

const KINDS: { id: FindingKind; label: string; tone: "ember" | "teal" | "navy" | "amber" }[] = [
  { id: "pain_point", label: "Pain points", tone: "ember" },
  { id: "requirement", label: "Requirements", tone: "teal" },
  { id: "constraint", label: "Constraints", tone: "navy" },
  { id: "open_question", label: "Open questions", tone: "amber" },
];

function FindingCard({ f, onReview }: { f: Finding; onReview: (f: Finding, r: Finding["review"]) => void }) {
  const wrong = f.review === "wrong";
  return (
    <Card testId={`finding-${f.id}`} className={`p-3.5 ${wrong ? "opacity-50" : ""} ${f.evidence_ok === false ? "border-ember/60" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold text-ink-3">{f.id}</span>
            <span className={`text-[13px] font-semibold ${wrong ? "line-through" : ""}`}>{f.title}</span>
          </div>
          <div className="mt-1 text-[12.5px] leading-snug text-ink-2">{f.detail}</div>
        </div>
        <div className="flex shrink-0 gap-1">
          <button aria-label="confirm" onClick={() => onReview(f, f.review === "confirmed" ? "unreviewed" : "confirmed")}
            className={`rounded-md p-1.5 ${f.review === "confirmed" ? "bg-teal text-white" : "text-ink-3 hover:bg-mist"}`}><ThumbsUp size={13} /></button>
          <button aria-label="wrong" onClick={() => onReview(f, wrong ? "unreviewed" : "wrong")}
            className={`rounded-md p-1.5 ${wrong ? "bg-ember text-white" : "text-ink-3 hover:bg-mist"}`}><ThumbsDown size={13} /></button>
        </div>
      </div>
      <div className={`mt-2.5 rounded-lg border-l-[3px] px-3 py-2 text-[12px] ${f.evidence_ok === false ? "border-ember bg-ember-50" : "border-teal bg-mist"}`}>
        <div className="italic text-ink">“{f.quote}”</div>
        <div className="mt-1 flex items-center justify-between">
          <span className="font-semibold text-ink-2">{f.speaker}</span>
          {f.evidence_ok === true && <span data-testid="evidence-ok" className="flex items-center gap-1 font-semibold text-teal"><CheckCircle2 size={12} /> Quote found in transcript</span>}
          {f.evidence_ok === false && <span data-testid="evidence-bad" className="flex items-center gap-1 font-semibold text-ember"><AlertTriangle size={12} /> Not found: check before using</span>}
        </div>
      </div>
      {(f.frequency || f.impact) && (
        <div className="mt-2 flex gap-3 text-[11.5px] text-ink-3">
          {f.frequency && <span>How often <b className="text-ink-2">{f.frequency}/5</b></span>}
          {f.impact && <span>How much it hurts <b className="text-ink-2">{f.impact}/5</b></span>}
        </div>
      )}
    </Card>
  );
}

export default function FindingsTab({ onChange }: { onChange: () => void }) {
  const [fs, setFs] = useState<Finding[]>([]);
  const [busy, setBusy] = useState(false);
  const [notBuilt, setNotBuilt] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api.get<Finding[]>("/api/findings").then(setFs); }, []);

  const extract = async () => {
    setBusy(true); setError(""); setNotBuilt("");
    try { setFs(await api.post<Finding[]>("/api/findings/extract")); onChange(); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNotBuilt(e.message); else setError(String((e as Error).message)); }
    finally { setBusy(false); }
  };
  const review = async (f: Finding, r: Finding["review"]) => {
    const u = await api.put<Finding>(`/api/findings/${f.id}`, { review: r });
    setFs((all) => all.map((x) => (x.id === u.id ? u : x))); onChange();
  };
  const ok = fs.filter((f) => f.evidence_ok === true).length;
  const bad = fs.filter((f) => f.evidence_ok === false).length;
  const reviewed = fs.filter((f) => f.review !== "unreviewed").length;

  return (
    <div>
      <Card className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-mist"><FileText size={17} className="text-ink-2" /></div>
          <div>
            <div className="text-[14px] font-semibold">Findings from the discovery transcript</div>
            <div className="text-[12.5px] text-ink-2">data/Day01_Slide21_discovery_transcript.md · the model drafts, the code checks every quote, you review</div>
          </div>
        </div>
        <Button onClick={extract} disabled={busy} testId="extract-findings">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <ScanSearch size={14} />} {fs.length ? "Extract again" : "Extract findings"}
        </Button>
      </Card>
      {notBuilt && <div className="mt-3"><NotBuilt ticket="ENG-101">{notBuilt}. Open docs/tickets/ENG-101.md: the screen is ready, the backend is not.</NotBuilt></div>}
      {error && <div className="mt-3 rounded-lg bg-ember-50 px-4 py-2 text-[12.5px] text-ember">{error}</div>}
      {fs.length > 0 && (
        <>
          <div className="mt-4 grid grid-cols-4 gap-3">
            <Kpi label="Findings" value={fs.length} sub={KINDS.map((k) => `${fs.filter((f) => f.kind === k.id).length} ${k.label.toLowerCase()}`).join(" · ")} />
            <Kpi label="Quotes verified" value={`${ok} / ${fs.length}`} sub="Found word for word in the transcript" tone="teal" />
            <Kpi label="Quotes not found" value={<span data-testid="bad-count">{bad}</span>} sub="Invented or misattributed: fix or drop" tone={bad ? "ember" : "ink"} />
            <Kpi label="Reviewed by you" value={`${reviewed} / ${fs.length}`} sub="Thumbs up or down on every card" />
          </div>
          <div className="mt-4 grid grid-cols-[1fr_400px] gap-4">
            <div className="grid grid-cols-2 gap-3">
              {KINDS.map((k) => (
                <div key={k.id} className="space-y-2.5">
                  <div className="flex items-center gap-2 px-1"><Chip tone={k.tone}>{k.label}</Chip><span className="text-[12px] text-ink-3">{fs.filter((f) => f.kind === k.id).length}</span></div>
                  {fs.filter((f) => f.kind === k.id).map((f) => <FindingCard key={f.id} f={f} onReview={review} />)}
                </div>
              ))}
            </div>
            <div className="space-y-3">
              <Card className="p-4">
                <div className="text-[13px] font-semibold">Pain-point matrix</div>
                <div className="text-[12px] text-ink-3">Top right: frequent and painful. Dashed: quote not found.</div>
                <PainMatrix findings={fs} />
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
