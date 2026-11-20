// Labelling with the expert: label 20 extracted values yourself, then measure how far you agree with Tom.
import { BookOpen, Check, RotateCcw, Scale, X } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ApiError, type Agreement, type LabelItem, type LabelRound } from "../../api";
import { Button, Card, NotBuilt } from "../../components/ui";
import { Matrix, PageCrop } from "../../components/evalViz";

const LABEL: Record<string, string> = { full_name: "Full name", address: "Address", statement_date: "Statement date", issuer: "Issuer" };
type Data = { items: LabelItem[]; guidelines: string; guideline_version: string; rounds: LabelRound[] };

export default function LabellingTab() {
  const [d, setD] = useState<Data | null>(null);
  const [res, setRes] = useState<{ agreement: Agreement; rounds: LabelRound[]; tom: Record<string, string> } | null>(null);
  const [nb, setNb] = useState("");
  const load = () => api.get<Data>("/api/eval/labelling").then(setD);
  useEffect(() => { load(); }, []);
  if (!d) return null;
  const done = d.items.filter((i) => i.label).length;
  const set = async (item: string, label: "correct" | "wrong") => {
    await api.put(`/api/eval/labelling/${item}`, { label });
    setD({ ...d, items: d.items.map((i) => (i.item === item ? { ...i, label } : i)) });
  };
  const compare = async () => {
    setNb("");
    try { setRes(await api.post("/api/eval/labelling/compare")); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; }
  };
  const again = async () => { await api.post("/api/eval/labelling/reset"); setRes(null); load(); };
  const a = res?.agreement;
  const rounds = res?.rounds ?? d.rounds;
  return (
    <div className="grid grid-cols-[300px_minmax(0,1fr)] gap-4">
      <div className="space-y-4">
        <Card className="p-4" testId="guidelines">
          <div className="flex items-center gap-2 text-[13px] font-semibold"><BookOpen size={15} /> Labelling guidelines</div>
          <div className="mt-0.5 text-[11.5px] text-ink-3">{d.guideline_version}</div>
          <div className="guide mt-2 max-h-[420px] overflow-auto text-[12px] leading-relaxed text-ink-2">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{d.guidelines.replace(/^# .*\n/m, "")}</ReactMarkdown>
          </div>
        </Card>
        <Card className="p-4" testId="rounds">
          <div className="text-[13px] font-semibold">Rounds</div>
          {rounds.length === 0 && <div className="mt-1 text-[12px] text-ink-2">Label all 20, then compare with Tom.</div>}
          {rounds.map((r) => (
            <div key={r.round} className="mt-2 flex items-center justify-between text-[12.5px]">
              <span>Round {r.round} <span className="text-ink-3">· {r.guideline}</span></span>
              <span className="font-semibold tabular-nums">{r.agreement.percent}% · κ {r.agreement.kappa}</span>
            </div>
          ))}
        </Card>
      </div>
      <div>
        <Card className="flex items-center justify-between px-4 py-3">
          <div>
            <div className="text-[14px] font-semibold">Label 20 values the prototype extracted: is each one correct?</div>
            <div className="text-[12.5px] text-ink-2">Decide from the document crop and the guidelines. Tom has labelled the same 20; you see his labels after you compare.</div>
          </div>
          <div className="flex items-center gap-2">
            <span data-testid="progress" className="text-[12.5px] font-semibold tabular-nums text-ink-2">{done} of {d.items.length}</span>
            {res ? <Button variant="secondary" onClick={again} testId="label-again"><RotateCcw size={14} /> Label again</Button>
              : <Button onClick={compare} disabled={done < d.items.length} testId="compare"><Scale size={14} /> Compare with Tom</Button>}
          </div>
        </Card>
        {nb && <div className="mt-3"><NotBuilt ticket="ENG-401">{nb}. Open docs/tickets/ENG-401.md.</NotBuilt></div>}
        {a && (
          <Card className="mt-3 grid grid-cols-[1fr_1fr_1.4fr] gap-4 p-4" testId="agreement">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">Agreement</div>
              <div className="mt-1 text-[30px] font-semibold leading-none" data-testid="percent">{a.percent}%</div>
              <div className="mt-1 text-[12px] text-ink-2">{a.agree} of {a.n} labels the same as Tom</div>
            </div>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">Cohen's kappa</div>
              <div className={`mt-1 text-[30px] font-semibold leading-none ${a.kappa >= 0.8 ? "text-teal" : a.kappa >= 0.6 ? "text-amber" : "text-ember"}`} data-testid="kappa">{a.kappa}</div>
              <div className="mt-1 text-[12px] text-ink-2">{a.kappa >= 0.8 ? "Strong: labels you can build on" : a.kappa >= 0.6 ? "Moderate: fix the guidelines" : "Weak: you and Tom mean different things"}</div>
            </div>
            <Matrix a={a} rater="You" expert="Tom" pos="wrong" neg="correct" testId="matrix" />
          </Card>
        )}
        <div className="mt-3 grid grid-cols-2 gap-3" data-testid="items">
          {d.items.map((it) => {
            const tom = res?.tom[it.item];
            const differ = !!res && tom !== it.label;
            return (
              <Card key={it.item} testId={`item-${it.item}`} className={`flex gap-3 p-3 ${differ ? "border-ember ring-2 ring-ember/20" : ""}`}>
                <PageCrop image={it.image} box={it.box} width={210} />
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] text-ink-3"><span className="font-mono">{it.item} · {it.case_id}</span> · {LABEL[it.field]}</div>
                  <div className="mt-0.5 text-[13.5px] font-semibold">{it.value || "—"}</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(["correct", "wrong"] as const).map((l) => (
                      <button key={l} data-testid={`${l}-${it.item}`} onClick={() => !res && set(it.item, l)}
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11.5px] font-semibold ${it.label === l ? (l === "correct" ? "bg-teal text-white" : "bg-ember text-white") : "bg-mist text-ink-2"}`}>
                        {l === "correct" ? <Check size={12} /> : <X size={12} />} {l}
                      </button>
                    ))}
                  </div>
                  {res && <div className={`mt-1.5 text-[11.5px] ${differ ? "font-semibold text-ember" : "text-ink-3"}`}>Tom: {tom}</div>}
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
