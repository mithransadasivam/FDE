// The latest headless Claude Code review (backend/scripts/pr_review.py writes engagement/reviews/latest.json).
import { Bot, FileCode2, Terminal } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type PrReview } from "../../api";
import { Card, Chip } from "../../components/ui";

const VERDICT = {
  looks_good: { tone: "teal", text: "Looks good" },
  comments: { tone: "amber", text: "Comments" },
  changes_needed: { tone: "ember", text: "Changes needed" },
} as const;
const SEV = { high: "ember", medium: "amber", low: "mist" } as const;

export default function PrReviewTab() {
  const [r, setR] = useState<PrReview | null>(null);
  const [none, setNone] = useState(false);
  useEffect(() => {
    api.get<PrReview>("/api/cases/pr-review").then(setR).catch((e) => { if (e instanceof ApiError && e.status === 404) setNone(true); });
  }, []);
  if (none) return (
    <Card className="p-5" testId="no-review">
      <div className="flex items-center gap-2 text-[14px] font-semibold"><Terminal size={16} /> No review yet</div>
      <div className="mt-1.5 text-[13px] text-ink-2">Run a headless review of your branch from <code>backend/</code>:</div>
      <pre className="mt-2 rounded-lg bg-navy px-3 py-2 text-[12.5px] text-white">python -m scripts.pr_review</pre>
    </Card>
  );
  if (!r) return null;
  const v = VERDICT[r.verdict];
  return (
    <div className="grid grid-cols-[320px_minmax(0,1fr)] gap-4">
      <Card className="p-4" testId="review-summary">
        <div className="flex items-center gap-2"><div className="grid h-9 w-9 place-items-center rounded-lg bg-navy"><Bot size={17} className="text-white" /></div>
          <div><div className="text-[14px] font-semibold">Claude review</div><div className="text-[11.5px] text-ink-3">headless · claude -p · {new Date(r.reviewed_at).toLocaleString("en-GB")}</div></div></div>
        <div className="mt-3"><Chip tone={v.tone}><span data-testid="verdict">{v.text}</span></Chip></div>
        <p className="mt-2.5 text-[13px] leading-relaxed">{r.summary}</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-[12px]">
          <div className="rounded-lg bg-mist px-2.5 py-2"><div className="text-ink-3">Changed</div><div className="font-semibold">{r.stats.files.length} files</div></div>
          <div className="rounded-lg bg-mist px-2.5 py-2"><div className="text-ink-3">Lines</div><div className="font-semibold"><span className="text-teal">+{r.stats.lines_added}</span> <span className="text-ember">−{r.stats.lines_removed}</span></div></div>
        </div>
        <div className="mt-3 text-[11.5px] text-ink-2">Claude comments; a person approves the merge.{r.cost_usd !== null && ` Cost of this review: $${r.cost_usd.toFixed(3)}.`}</div>
      </Card>
      <Card className="overflow-hidden" testId="findings">
        <div className="px-4 pt-3 text-[13px] font-semibold">Findings, most severe first</div>
        {r.findings.length === 0 && <div className="px-4 py-3 text-[13px] text-teal">Nothing to report.</div>}
        {r.findings.map((f, i) => (
          <div key={i} data-testid="finding" className="mt-2 border-t border-black/[0.05] px-4 py-3">
            <div className="flex items-center gap-2 text-[12px]">
              <Chip tone={SEV[f.severity]}>{f.severity}</Chip>
              <FileCode2 size={13} className="text-ink-3" /><code className="text-ink-2">{f.file}{f.line ? `:${f.line}` : ""}</code>
              <span className="ml-auto text-ink-3">{f.rule}</span>
            </div>
            <div className="mt-1.5 text-[13px] leading-relaxed">{f.message}</div>
          </div>
        ))}
      </Card>
    </div>
  );
}
