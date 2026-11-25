// Read a document (Activity 2, ticket ENG-1102): the small model's label for every word, the four fields, and how sure
// it is of each. A field's confidence must say how likely the value is to be right: a smudged date must not look sure.
import { AlertTriangle, Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type SmallDoc, type SmallEval } from "../../api";
import { Card, Chip, Kpi } from "../../components/ui";
import PageView, { type Box } from "../pipeline/PageView";
import { Bar, FIELD_NAMES, ModelPicker, TicketChips11, pct, useDistil } from "./parts";

type DocRow = { doc_id: string; kind: string; slices: string[] };
const TONE: Record<string, Box["tone"]> = { full_name: "navy", address: "teal", statement_date: "amber", issuer: "navy" };

export default function ReadTab() {
  const { st } = useDistil();
  const [model, setModel] = useState<string | null>(null);
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [filter, setFilter] = useState<"all" | "smudge" | "errors">("smudge");
  const [docId, setDocId] = useState(() => window.location.hash.split("/")[3] || "B-012");
  const [doc, setDoc] = useState<SmallDoc | null>(null);
  const [ev, setEv] = useState<SmallEval | null>(null);
  useEffect(() => { if (st && !model) setModel(st.active); }, [st]);
  useEffect(() => { api.get<{ documents: DocRow[] }>("/api/pipeline/documents?set=october").then((r) => setDocs(r.documents)); }, []);
  useEffect(() => {
    if (!model) return;
    api.get<SmallEval>(`/api/distil/evaluate?set=october&model=${model}&threshold=${st?.threshold ?? 0.7}`).then(setEv);
  }, [model]);
  useEffect(() => {
    if (!model) return;
    window.history.replaceState(null, "", `#/modellab/read/${docId}`);
    api.get<SmallDoc>(`/api/distil/documents/${docId}?model=${model}`).then(setDoc);
  }, [model, docId]);
  if (!st) return null;
  const errDocs = new Set(ev?.errors.map((e) => e.doc_id) ?? []);
  const shown = docs.filter((d) => filter === "all" || (filter === "smudge" ? d.slices.includes("smudge") : errDocs.has(d.doc_id)));
  const th = doc?.threshold ?? st.threshold;
  const boxes: Box[] = (doc?.words ?? []).filter((w) => w.label && w.label !== "O").map((w) => ({
    box: w.box, tone: (w.p ?? 0) * w.confidence < th ? "ember" : TONE[w.label!], title: `${w.text}: ${w.label} ${w.p} · OCR ${w.confidence}`,
  }));
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><TicketChips11 st={st} /><span className="ml-auto text-[12px] text-ink-3">Model</span>
        <ModelPicker st={st} value={model} onChange={setModel} /></div>
      {ev && ev.model && (
        <div className="grid grid-cols-4 gap-3" data-testid="eval-kpis">
          <Kpi label="Fields right, small model alone" value={pct(ev.overall)} sub={`${ev.overall.right} of ${ev.overall.fields}, October`} />
          <Kpi label="Errors" value={ev.overall.fields - ev.overall.right} sub="against Tom's keyed labels" tone="amber" />
          <Kpi label={`Errors it is sure of (≥ ${th.toFixed(2)})`} value={<span data-testid="confident-errors">{ev.confident_errors}</span>}
            sub={ev.confident_errors ? "these would go straight through" : "every error says it is unsure"} tone={ev.confident_errors ? "ember" : "teal"} />
          <Kpi label="Time to read a document" value={`${ev.ms_per_doc} ms`} sub="features, model and fields, on this laptop" tone="teal" />
        </div>
      )}
      <div className="grid grid-cols-[220px_1fr_430px] gap-4">
        <Card className="overflow-hidden">
          <div className="flex gap-1 border-b border-black/[0.05] p-2 text-[11.5px]">
            {(["smudge", "errors", "all"] as const).map((f) => (
              <button key={f} data-testid={`filter-${f}`} onClick={() => setFilter(f)} className={`rounded-md px-2 py-1 font-semibold ${filter === f ? "bg-navy text-white" : "text-ink-2 hover:bg-mist"}`}>
                {f === "smudge" ? "Smudged" : f === "errors" ? "Errors" : "All"}</button>
            ))}
          </div>
          <div className="max-h-[600px] overflow-y-auto">
            {shown.map((d) => (
              <button key={d.doc_id} data-testid={`doc-${d.doc_id}`} onClick={() => setDocId(d.doc_id)}
                className={`block w-full border-t border-black/[0.04] px-3 py-1.5 text-left text-[12px] ${d.doc_id === docId ? "bg-teal-50" : "hover:bg-mist/60"}`}>
                <span className="font-mono font-semibold">{d.doc_id}</span> <span className="text-ink-3">{d.kind === "bank_statement" ? "statement" : "bill"}</span>
                {errDocs.has(d.doc_id) && <span className="ml-1 text-ember">●</span>}
              </button>
            ))}
          </div>
        </Card>
        <div>{doc && <PageView src={doc.image} boxes={boxes} testId="ml-page" height={620} />}
          <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-ink-2">
            <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm border border-navy bg-navy/10" />name, issuer</span>
            <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm border border-teal bg-teal/10" />address</span>
            <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm border border-amber bg-amber/15" />statement date</span>
            <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm border border-ember bg-ember/15" />probability × OCR confidence below {th.toFixed(2)}</span>
          </div></div>
        <div className="space-y-3">
          {doc && doc.fields && (
            <Card className="p-4" testId="ml-fields">
              <div className="flex items-baseline gap-2"><span className="font-mono text-[14px] font-semibold">{doc.doc_id}</span>
                <span className="text-[12px] text-ink-3">{doc.source === "ocr" ? "a scan: words from the bank's OCR" : "a digital PDF: exact words"}</span>
                {doc.slices.includes("smudge") && <Chip tone="amber">smudged</Chip>}</div>
              <div className="mt-3 space-y-3">
                {doc.fields.map((f) => (
                  <div key={f.name} data-testid={`mf-${f.name}`}>
                    <div className="flex items-center gap-2 text-[12px]"><span className="font-semibold">{FIELD_NAMES[f.name]}</span>
                      <span className="ml-auto font-mono text-[12px]" data-testid={`conf-${f.name}`}>{f.confidence.toFixed(2)}</span></div>
                    <Bar value={f.confidence} max={1} tone={f.confidence < th ? "ember" : "teal"} />
                    <div className="mt-1 flex items-start gap-1.5 text-[12.5px]">
                      {f.correct ? <Check size={14} className="mt-0.5 shrink-0 text-teal" /> : <X size={14} className="mt-0.5 shrink-0 text-ember" />}
                      <span className="font-mono" data-testid={`val-${f.name}`}>{f.value || "(nothing)"}</span></div>
                    {!f.correct && <div className="ml-5 text-[11.5px] text-ink-3">Tom's label: <span className="font-mono">{doc.expected[f.name]}</span></div>}
                  </div>
                ))}
              </div>
              {doc.decision && (
                <div className={`mt-3 rounded-lg px-3 py-2 text-[12px] ${doc.decision.route === "small" ? "bg-teal-50" : "bg-amber-50"}`} data-testid="ml-decision">
                  <b>{doc.decision.route === "small" ? "Straight through on the small model" : "To the pilot"}</b> at {th.toFixed(2)}
                  {doc.decision.reasons.length > 0 && <span>: {doc.decision.reasons.join(" · ")}</span>}
                </div>
              )}
            </Card>
          )}
          {ev && ev.errors.length > 0 && (
            <Card className="overflow-hidden" testId="ml-errors">
              <div className="flex items-center gap-2 px-4 py-2 text-[13px] font-semibold"><AlertTriangle size={14} className="text-amber" />The small model's errors, surest first</div>
              <table className="w-full text-[11.5px]">
                <tbody>{ev.errors.slice(0, 9).map((e) => (
                  <tr key={e.doc_id + e.field} className="cursor-pointer border-t border-black/[0.05] hover:bg-mist/60" onClick={() => setDocId(e.doc_id)}>
                    <td className="px-3 py-1 font-mono">{e.doc_id}</td><td>{FIELD_NAMES[e.field]}</td><td className="font-mono">{e.value || "–"}</td>
                    <td className={`px-3 text-right font-mono font-semibold ${e.confidence >= th ? "text-ember" : "text-ink-3"}`}>{e.confidence.toFixed(2)}</td></tr>))}</tbody>
              </table>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
