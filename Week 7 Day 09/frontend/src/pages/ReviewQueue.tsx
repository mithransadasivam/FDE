// Review queue: the fields the pipeline is not sure of, for the KYC analysts to check (Day 6). The client's screen.
import { Check, ChevronRight, Eye, PencilLine } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Queue, type RoutedItem } from "../api";
import { Button, Card, Chip } from "../components/ui";
import PageView from "./pipeline/PageView";
import { useDocSet } from "./pipeline/useDocSet";

const key = (i: RoutedItem) => `${i.doc_id}/${i.field}`;

export default function ReviewQueue() {
  const [set] = useDocSet();
  const [q, setQ] = useState<Queue | null>(null);
  const [sel, setSel] = useState("");
  const [text, setText] = useState("");
  const [show, setShow] = useState<"open" | "done">("open");
  const load = () => api.get<Queue>(`/api/pipeline/queue?set=${set}`).then((x) => {
    setQ(x);
    const first = x.items.find((i) => !i.reviewed);
    setSel((s) => (s && x.items.some((i) => key(i) === s && !i.reviewed) ? s : first ? key(first) : ""));
  });
  useEffect(() => { load(); }, []);
  const item = q?.items.find((i) => key(i) === sel);
  useEffect(() => { setText(item?.value ?? ""); }, [sel]);
  if (!q) return null;
  const act = async (action: "accept" | "correct", value: string) => {
    if (!item) return;
    await api.post("/api/pipeline/review", { set, doc_id: item.doc_id, field: item.field, action, value, analyst_id: "tom-team" });
    await load();
  };
  const list = q.items.filter((i) => (show === "open" ? !i.reviewed : !!i.reviewed));
  const total = q.open + q.done;
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">Client workspace <ChevronRight size={13} /> <span className="text-ink-2">Review queue</span></div>
      <div className="mt-1 flex items-end justify-between">
        <div>
          <h1 className="text-[24px] font-semibold tracking-tight">Review queue: fields to check</h1>
          <div className="text-[12.5px] text-ink-2">Set: <span className="font-mono">{set}</span> (chosen on Pipeline). Every other field went straight through: it was read clearly, and both methods agree.</div>
        </div>
        <div data-testid="queue-progress" className="text-right">
          <div className="text-[22px] font-semibold">{q.done} <span className="text-[14px] font-normal text-ink-3">of {total} checked</span></div>
          <div className="mt-1 h-1.5 w-56 rounded-full bg-mist"><div className="h-1.5 rounded-full bg-teal" style={{ width: `${total ? (100 * q.done) / total : 0}%` }} /></div>
        </div>
      </div>
      {q.empty ? <Card className="mt-4 p-5 text-[13px] text-ink-2" testId="queue-empty">{q.empty}.</Card> : (
        <div className="mt-4 grid grid-cols-[300px_minmax(0,1fr)_320px] gap-4">
          <Card className="overflow-hidden" testId="queue-list">
            <div className="flex gap-1 border-b border-black/[0.05] p-2">
              {(["open", "done"] as const).map((s) => (
                <button key={s} data-testid={`queue-${s}`} onClick={() => setShow(s)} className={`flex-1 rounded-md py-1 text-[12px] font-semibold ${show === s ? "bg-navy text-white" : "bg-mist text-ink-2"}`}>
                  {s === "open" ? `To check (${q.open})` : `Checked (${q.done})`}</button>
              ))}
            </div>
            <div className="max-h-[640px] overflow-auto">
              {list.map((i) => (
                <div key={key(i)} data-testid={`qi-${i.doc_id}-${i.field}`} onClick={() => setSel(key(i))}
                  className={`cursor-pointer border-b border-black/[0.04] px-3 py-2 ${sel === key(i) ? "bg-amber-50/70" : "hover:bg-mist/60"}`}>
                  <div className="flex items-center justify-between text-[12px]"><span className="font-mono font-semibold">{i.doc_id}</span><span className="text-ink-3">{i.label}</span></div>
                  <div className="truncate text-[12.5px] font-semibold">{i.reviewed ? i.reviewed.value : i.value || "—"}</div>
                  <div className="truncate text-[11px] text-ink-3">{i.reasons[0]}</div>
                </div>
              ))}
              {!list.length && <div className="p-4 text-[12.5px] text-ink-3">{show === "open" ? "Nothing left to check." : "Nothing checked yet."}</div>}
            </div>
          </Card>
          <Card className="p-3">
            {item ? <PageView src={`/api/pipeline/documents/${item.doc_id}/image`} testId="queue-page" height={600}
              boxes={item.box ? [{ box: item.box, tone: "amber" }] : []} /> : <div className="grid h-full place-items-center text-ink-3">Pick a field</div>}
          </Card>
          <Card className="min-w-0 break-words p-4" testId="queue-item">
            {item && (
              <div className="space-y-3">
                <div><div className="font-mono text-[12px] text-ink-3">{item.doc_id}</div><div className="text-[17px] font-semibold">{item.label}</div></div>
                <div className="rounded-lg bg-amber-50 p-2.5 text-[12px]">
                  <div className="font-semibold text-amber">Why you are seeing this</div>
                  {item.reasons.map((r) => <div key={r} className="mt-0.5 text-ink-2">{r}</div>)}
                </div>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">Read from the words</div>
                  <div className="text-[14px] font-semibold">{item.value || "—"} {item.confidence > 0 && <Chip>{item.confidence.toFixed(2)}</Chip>}</div>
                </div>
                {item.vision != null && (
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">The vision model read</div>
                    <div className="text-[14px] font-semibold">{item.vision || "—"}</div>
                  </div>
                )}
                {item.reviewed ? (
                  <div className="rounded-lg bg-teal-50 p-2.5 text-[12px] text-teal" data-testid="queue-done">Checked by {item.reviewed.analyst_id}: {item.reviewed.action === "accept" ? "accepted" : "corrected to"} “{item.reviewed.value}”.</div>
                ) : (
                  <div className="space-y-2 border-t border-black/[0.05] pt-3">
                    <Button onClick={() => act("accept", item.value)} testId="q-accept"><Check size={14} /> The words are right</Button>
                    {item.vision && item.vision !== item.value && <Button variant="secondary" onClick={() => act("correct", item.vision!)} testId="q-vision"><Eye size={14} /> Use the vision model's value</Button>}
                    <div className="flex gap-2">
                      <input data-testid="q-correct-input" value={text} onChange={(e) => setText(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-black/10 px-2 py-1.5 text-[12.5px]" />
                      <Button variant="secondary" onClick={() => act("correct", text)} disabled={!text.trim()} testId="q-correct"><PencilLine size={14} /> Correct</Button>
                    </div>
                    <div className="text-[11px] text-ink-3">Check against the page, not against either reading.</div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
