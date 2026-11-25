// The analyst's review screen: the document with its field boxes on the left, the fields, rules and decision on the right.
import { AlertCircle, ArrowLeft, Check, CheckCircle2, CircleDashed, Copy, FileImage, Loader2, Minus, Plus, Undo2, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type CaseDetail, type CaseField, type PolicyCheck } from "../../api";
import FieldBoxes from "../../components/FieldBoxes";
import { Button, Card, NotBuilt } from "../../components/ui";

const ANALYST = { id: "TR-014", name: "Tom Reyes" };
const BAR = { ok: "bg-teal", check: "bg-amber", doubtful: "bg-ember", not_on_page: "bg-ember", missing: "bg-ember", confirmed: "bg-navy" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmt = (iso: string) => { const [y, m, d] = iso.split("-"); return `${d} ${MONTHS[Number(m) - 1]} ${y}`; };

function CheckRow({ c }: { c: PolicyCheck }) {
  const I = c.status === "pass" ? CheckCircle2 : c.status === "fail" ? XCircle : CircleDashed;
  const col = c.status === "pass" ? "text-teal" : c.status === "fail" ? "text-ember" : "text-amber";
  return (
    <div data-testid={`check-${c.id}`} data-status={c.status} className="flex gap-2.5 py-1.5">
      <I size={17} className={`mt-[1px] shrink-0 ${col}`} />
      <div>
        <div className={`text-[13px] ${c.status === "pass" ? "text-ink" : `font-semibold ${col}`}`}>{c.label}</div>
        {c.detail && <div className="text-[12px] text-ink-2">{c.detail}</div>}
      </div>
    </div>
  );
}

// S06: copies the value exactly as it is on screen, so typing into CaseFlow is a paste.
function CopyButton({ f }: { f: CaseField }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number>();
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const copy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(f.value);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked: the value is still on screen to select by hand */ }
  };
  const label = `Copy ${f.label.toLowerCase()}`;
  return (
    <>
      <button type="button" data-testid={`copy-${f.name}`} data-copied={copied} disabled={!f.value} onClick={copy}
        aria-label={copied ? `Copied ${f.label.toLowerCase()}` : label} title={f.value ? label : "Nothing to copy"}
        className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-[11.5px] font-semibold text-ink-2 hover:bg-mist disabled:cursor-not-allowed disabled:text-ink-3/50 disabled:hover:bg-transparent">
        {copied ? <Check size={12} className="text-teal" /> : <Copy size={12} />}
        {copied ? "Copied" : "Copy"}
      </button>
      <span role="status" className="sr-only">{copied ? `${f.label} copied` : ""}</span>
    </>
  );
}

function FieldRow({ f, selected, onSelect, act }: {
  f: CaseField; selected: boolean; onSelect: () => void; act: (action: "accept" | "correct", value?: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(f.value);
  const needs = !["ok", "confirmed"].includes(f.status);
  const tone = f.status === "check" ? "amber" : "ember";
  const head = { check: "check needed", doubtful: "doubtful: read it on the page", not_on_page: "not what the page says", missing: "not found" }[f.status as string];
  return (
    <div data-testid={`field-${f.name}`} data-selected={selected} onClick={onSelect}
      className={`cursor-pointer border-b border-black/[0.05] py-3 last:border-0 ${selected && !needs ? "-mx-2 rounded-lg bg-mist px-2" : ""}`}>
      {!needs ? (
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[12px] text-ink-3">{f.label}{f.status === "confirmed" && <span className="ml-1.5 text-navy">· {f.note}</span>}</div>
            <div className="text-[14.5px] font-medium">{f.value}</div>
          </div>
          <div className="flex shrink-0 items-center gap-2 pt-1">
            <CopyButton f={f} />
            {f.status === "confirmed" ? <Check size={15} className="text-navy" /> : <>
              <div className="h-1.5 w-16 rounded-full bg-mist"><div className={`h-1.5 rounded-full ${BAR[f.status]}`} style={{ width: `${f.confidence * 100}%` }} /></div>
              <span className="w-8 text-right text-[13px] font-semibold tabular-nums text-teal">{f.confidence.toFixed(2)}</span>
            </>}
          </div>
        </div>
      ) : (
        <div className={`rounded-xl border p-3 ${tone === "amber" ? "border-amber/50 bg-amber-50" : "border-ember/40 bg-ember-50"}`}>
          <div className={`flex items-center gap-1.5 text-[13px] font-semibold ${tone === "amber" ? "text-amber" : "text-ember"}`}>
            <AlertCircle size={15} /> {f.label} · {head}
            {f.confidence > 0 && <span className="ml-auto tabular-nums">{f.confidence.toFixed(2)}</span>}
          </div>
          <div className="mt-1.5 flex items-center justify-between gap-2">
            <div className="text-[15px] font-medium">{f.value || "—"}</div>
            <CopyButton f={f} />
          </div>
          {f.note && <div className="mt-1 text-[12px] text-ink-2">{f.note}. Look at the box on the page before you decide.</div>}
          {!f.note && <div className="mt-1 text-[12px] text-ink-2">The OCR was not sure of every word. Look at the box on the page before you decide.</div>}
          {editing ? (
            <div className="mt-2.5 flex gap-2" onClick={(e) => e.stopPropagation()}>
              <input data-testid={`correct-input-${f.name}`} value={text} onChange={(e) => setText(e.target.value)} autoFocus
                className="min-w-0 flex-1 rounded-lg border border-black/15 bg-white px-2.5 py-1.5 text-[13px] outline-none focus:border-navy" />
              <Button testId={`correct-save-${f.name}`} onClick={() => act("correct", text)} disabled={!text.trim()}>Save</Button>
            </div>
          ) : (
            <div className="mt-2.5 flex gap-2" onClick={(e) => e.stopPropagation()}>
              {f.status === "not_on_page" && f.page_text ? (
                <Button testId={`accept-${f.name}`} onClick={() => act("correct", f.page_text)}><Check size={14} /> Use the page: {f.page_text}</Button>
              ) : f.value ? (
                <button data-testid={`accept-${f.name}`} onClick={() => act("accept")}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-teal px-3 py-2 text-[12.5px] font-semibold text-white hover:opacity-90"><Check size={14} /> Accept {f.value}</button>
              ) : null}
              <Button variant="secondary" testId={`correct-${f.name}`} onClick={() => { setText(f.page_text || f.value); setEditing(true); }}>Correct value</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CaseReview({ caseId, back }: { caseId: string; back: () => void }) {
  const [c, setC] = useState<CaseDetail | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [asking, setAsking] = useState<"ask_applicant" | "escalate" | null>(null);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => { api.get<CaseDetail>(`/api/cases/${caseId}`).then(setC); }, [caseId]);
  if (!c) return <div className="flex items-center gap-2 text-[13px] text-ink-2"><Loader2 size={14} className="animate-spin" /> Reading the document…</div>;

  const run = async (p: Promise<CaseDetail>) => {
    setErr("");
    try { setC(await p); } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); }
  };
  const act = (name: string) => (action: "accept" | "correct", value = "") =>
    run(api.post<CaseDetail>(`/api/cases/${caseId}/fields/${name}`, { action, value, analyst_id: ANALYST.id }));
  const decide = (decision: string, why = "") =>
    run(api.post<CaseDetail>(`/api/cases/${caseId}/decision`, { decision, analyst_id: ANALYST.id, reason: why })).then(() => setAsking(null));
  const firstFail = c.checks?.find((k) => k.status === "fail");
  const a = c.application;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_440px] gap-4">
      <Card className="flex min-h-[760px] flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-black/[0.06] px-4 py-2.5">
          <button onClick={back} className="rounded-md p-1 text-ink-3 hover:bg-mist"><ArrowLeft size={16} /></button>
          <FileImage size={16} className="text-ink-2" />
          <span className="whitespace-nowrap text-[13.5px] font-semibold">{c.document.file}</span>
          <div className="ml-auto flex items-center gap-3 whitespace-nowrap text-[11.5px] text-ink-2">
            <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-teal" />≥ 0.85</span>
            <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-amber" />0.60–0.85</span>
            <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-ember" />&lt; 0.60 or not on the page</span>
            <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-navy" />confirmed</span>
            <span className="ml-1 flex items-center rounded-lg border border-black/10">
              <button className="px-1.5 py-1" onClick={() => setZoom(Math.max(70, zoom - 10))}><Minus size={13} /></button>
              <span className="w-10 text-center tabular-nums">{zoom}%</span>
              <button className="px-1.5 py-1" onClick={() => setZoom(Math.min(160, zoom + 10))}><Plus size={13} /></button>
            </span>
          </div>
        </div>
        <div className="flex-1 overflow-auto bg-[#E9EBF2] p-6">
          <div data-testid="page" className="relative mx-auto shadow-[0_4px_18px_rgba(27,31,59,0.18)]" style={{ width: `${6.6 * zoom}px` }}>
            <img data-testid="doc-image" src={c.document.image} alt={`Document for ${caseId}`} className="block w-full" />
            {c.fields && <FieldBoxes fields={c.fields} selected={sel} onSelect={setSel} />}
          </div>
        </div>
      </Card>

      <Card className="flex flex-col">
        <div className="border-b border-black/[0.06] px-5 py-4">
          <div className="text-[17px] font-semibold">{caseId} · {a.applicant_name}</div>
          <div className="mt-0.5 text-[12.5px] text-ink-2">Applied {fmt(a.application_date)} · document received {fmt(a.received_date)} · {a.channel}</div>
          <div data-testid="application" className="mt-2 rounded-lg bg-mist px-3 py-2 text-[12.5px]"><span className="text-ink-3">On the application: </span>{a.address_line1}, {a.town}, {a.postcode}</div>
        </div>
        <div className="flex-1 px-5 py-1">
          {c.not_built.length > 0 && <div className="my-3"><NotBuilt ticket={c.not_built[0].includes("ENG-302") ? "ENG-302" : "ENG-301"}>{c.not_built[0]}</NotBuilt></div>}
          {c.fields?.map((f) => <FieldRow key={f.name + f.status} f={f} selected={sel === f.name} onSelect={() => setSel(f.name)} act={act(f.name)} />)}
          {c.checks && (
            <div className="mt-3" data-testid="checks">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-3">The bank's rules</div>
              {c.checks.map((k) => <CheckRow key={k.id} c={k} />)}
            </div>
          )}
        </div>
        <div className="border-t border-black/[0.06] px-5 py-4">
          {err && <div className="mb-2 text-[12px] font-semibold text-ember">{err}</div>}
          {c.decision ? (
            <div data-testid="decision" className="rounded-lg bg-navy px-3 py-2.5 text-[13px] text-white">
              {{ approve: "Approved", ask_applicant: "Asked the applicant", escalate: "Escalated" }[c.decision.decision]} by {c.decision.analyst_id}
              {c.decision.reason && <span className="text-white/70"> · {c.decision.reason}</span>}
            </div>
          ) : asking ? (
            <div>
              <div className="text-[12px] font-semibold text-ink-2">{asking === "escalate" ? "Why escalate?" : "What should the applicant send?"}</div>
              <textarea data-testid="reason-input" value={reason} onChange={(e) => setReason(e.target.value)} rows={2}
                className="mt-1 w-full rounded-lg border border-black/15 px-2.5 py-1.5 text-[13px] outline-none focus:border-navy" />
              <div className="mt-2 flex gap-2">
                <Button testId="confirm-decision" onClick={() => decide(asking, reason)} disabled={!reason.trim()}>Send</Button>
                <Button variant="ghost" onClick={() => setAsking(null)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <button data-testid="decide-approve" disabled={c.recommendation !== "ready"} onClick={() => decide("approve")}
                className="flex-1 rounded-xl bg-teal px-3 py-2.5 text-[14px] font-semibold text-white disabled:bg-[#B8BCCB]">Approve document</button>
              <Button variant="secondary" testId="decide-ask" onClick={() => { setReason(firstFail ? firstFail.detail : ""); setAsking("ask_applicant"); }}><Undo2 size={14} /> Ask applicant</Button>
              <Button variant="ghost" testId="decide-escalate" onClick={() => { setReason(""); setAsking("escalate"); }}>Escalate</Button>
            </div>
          )}
          <div className="mt-2.5 text-[11.5px] text-ink-3">Signed in as {ANALYST.name} · analyst {ANALYST.id}. You make the decision; every accept, correction and decision is logged.</div>
        </div>
      </Card>
    </div>
  );
}
