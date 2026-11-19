// Parse: what the bank sent, and where each document's words come from (ticket ENG-601).
import { FileImage, FileText, Loader2, ScanLine } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type DocList, type ParsedDoc } from "../../api";
import { Card, Chip, Kpi, NotBuilt } from "../../components/ui";
import PageView from "./PageView";

const FILTERS = [
  { id: "all", label: "All" }, { id: "digital", label: "Digital PDFs" }, { id: "scanned_pdf", label: "Scanned PDFs" }, { id: "jpg", label: "JPG scans" },
] as const;
type Filter = (typeof FILTERS)[number]["id"];
const SLICE: Record<string, string> = { two_dates: "two dates", joint_names: "joint names", smudge: "smudge" };

export default function ParseTab({ set }: { set: string }) {
  const [d, setD] = useState<DocList | null>(null);
  const [sel, setSel] = useState<string>("");
  const [doc, setDoc] = useState<ParsedDoc | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  useEffect(() => { api.get<DocList>(`/api/pipeline/documents?set=${set}`).then((x) => { setD(x); setSel(x.documents[0]?.doc_id ?? ""); setDoc(null); }); }, [set]);
  useEffect(() => { if (sel && d && !d.not_built) api.get<ParsedDoc>(`/api/pipeline/documents/${sel}`).then(setDoc); }, [sel, d]);
  const rows = useMemo(() => (d?.documents ?? []).filter((r) => {
    const pdf = r.file.endsWith(".pdf");
    if (filter === "digital") return pdf && r.source === "text_layer";
    if (filter === "scanned_pdf") return pdf && r.source === "ocr";
    if (filter === "jpg") return !pdf;
    return true;
  }), [d, filter]);
  if (!d) return <Card className="flex items-center gap-2 p-5 text-[12.5px] text-ink-2" testId="parsing"><Loader2 size={15} className="animate-spin" /> Parsing the 200 documents…</Card>;
  const pdfs = d.files.pdf ?? 0, jpgs = d.files.jpg ?? 0;
  const scannedPdf = d.documents.filter((r) => r.file.endsWith(".pdf") && r.source === "ocr").length;
  const built = !d.not_built;
  const KIND: Record<string, string> = { utility_bill: "bills", bank_statement: "bank statements", council_tax: "council tax bills" };
  const counts: Record<string, number> = {};
  d.documents.forEach((r) => { counts[r.kind] = (counts[r.kind] ?? 0) + 1; });
  const kinds = Object.entries(counts).map(([k, n]) => `${n} ${KIND[k] ?? k.replace(/_/g, " ")}`).join(" · ");
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3" data-testid="parse-kpis">
        <Kpi label="Documents" value={d.documents.length} sub={kinds} />
        <Kpi label="Files the bank sent" value={`${pdfs} PDF · ${jpgs} JPG`} sub="As they arrived in the KYC mailbox" />
        <Kpi label="Read from the text layer" value={built ? d.sources.text_layer ?? 0 : "—"} tone="teal" sub="Digital PDFs: exact words, confidence 1.00" />
        <Kpi label="Read from the bank's OCR" value={built ? d.sources.ocr ?? 0 : "—"} tone="amber"
          sub={built ? `${jpgs} JPG scans and ${scannedPdf} PDFs with no text layer` : "JPG scans, and PDFs with no text layer"} />
      </div>
      {!built && <NotBuilt ticket="ENG-601">{d.not_built}. Open docs/tickets/ENG-601.md.</NotBuilt>}
      <div className="grid grid-cols-[1.25fr_1fr] gap-4">
        <Card className="overflow-hidden" testId="doc-table">
          <div className="px-4 py-3">
            <div className="text-[13.5px] font-semibold">{d.set.label}</div>
            <div className="text-[12px] text-ink-2">From <span className="font-mono">{d.set.documents}</span>. Click a document to see its words.</div>
            <div className="mt-2 flex gap-1">
              {FILTERS.map((f) => (
                <button key={f.id} data-testid={`filter-${f.id}`} onClick={() => setFilter(f.id)}
                  className={`rounded-md px-2 py-1 text-[11.5px] font-semibold ${filter === f.id ? "bg-navy text-white" : "bg-mist text-ink-2"}`}>{f.label}</button>
              ))}
            </div>
          </div>
          <div className="max-h-[600px] overflow-auto">
            <table className="w-full text-left text-[12px]">
              <thead className="sticky top-0 bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
                <tr><th className="px-4 py-1.5">Document</th><th>Kind</th><th>File</th><th>Read from</th><th className="text-right">Words</th><th className="text-right">Below 0.85</th><th className="pl-3">Slices</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.doc_id} data-testid={`doc-${r.doc_id}`} onClick={() => setSel(r.doc_id)}
                    className={`cursor-pointer border-t border-black/[0.05] ${sel === r.doc_id ? "bg-amber-50/70" : "hover:bg-mist/60"}`}>
                    <td className="px-4 py-1.5 font-mono font-semibold">{r.doc_id}</td>
                    <td>{r.kind === "utility_bill" ? "Bill" : r.kind === "bank_statement" ? "Statement" : r.kind}</td>
                    <td className="font-mono text-[11px] text-ink-2">{r.file}</td>
                    <td>{r.source ? <Chip tone={r.source === "text_layer" ? "teal" : "amber"}>{r.source === "text_layer" ? "text layer" : "OCR"}</Chip> : <span className="text-ink-3">—</span>}</td>
                    <td className="text-right tabular-nums">{r.words ?? "—"}</td>
                    <td className={`text-right tabular-nums ${r.low_words ? "font-semibold text-amber" : "text-ink-3"}`}>{r.low_words ?? "—"}</td>
                    <td className="pl-3 text-[11px] text-ink-3">{r.slices.filter((s) => SLICE[s]).map((s) => SLICE[s]).join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card className="p-4" testId="doc-viewer">
          {doc && built ? (
            <>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[13.5px] font-semibold">
                  {doc.source === "text_layer" ? <FileText size={15} /> : doc.file.endsWith(".pdf") ? <ScanLine size={15} /> : <FileImage size={15} />}
                  <span className="font-mono">{doc.file}</span>
                </div>
                <Chip tone={doc.source === "text_layer" ? "teal" : "amber"} >{doc.source === "text_layer" ? "Text layer" : "Bank OCR"} · {doc.words.length} words</Chip>
              </div>
              <div className="mb-2 mt-1 text-[11.5px] text-ink-2">
                {doc.source === "text_layer" ? "A digital PDF: the words and their positions are in the file itself." :
                  doc.file.endsWith(".pdf") ? "A PDF with no text layer: a picture of a page. The words come from the bank's OCR file." :
                    "A JPG scan: the words come from the bank's OCR file."}{" "}
                <span className="text-teal">■</span> sure <span className="text-amber">■</span> below 0.85 <span className="text-ember">■</span> below 0.60
              </div>
              <PageView src={doc.image} testId="doc-page" height={560}
                boxes={doc.words.map((w) => ({ box: w.box, tone: w.confidence < 0.6 ? "ember" : w.confidence < 0.85 ? "amber" : "teal", title: `${w.id} · ${w.text} · ${w.confidence.toFixed(2)}` }))} />
            </>
          ) : <div className="grid h-full place-items-center text-[12.5px] text-ink-3">The words appear here once ENG-601 is built.</div>}
        </Card>
      </div>
    </div>
  );
}
