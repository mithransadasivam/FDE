// One success criterion: baseline → target, how it is measured, and what is missing.
import { ArrowDownRight, ArrowUpRight, CheckCircle2, CircleAlert, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import type { Criterion } from "../api";
import { Button, Card, Chip } from "./ui";

const KIND_TONE = { business: "navy", quality: "teal", guardrail: "amber" } as const;
const FIELDS: [keyof Criterion, string][] = [
  ["name", "Name"], ["metric", "Metric: what exactly is counted or timed"], ["baseline", "Baseline (today)"],
  ["target", "Target"], ["unit", "Unit"], ["measured_how", "Measured how"], ["owner", "Owner"], ["by_when", "By when"],
];

export default function CriterionCard({ c, onSave, onDelete }: { c: Criterion; onSave: (c: Criterion) => void; onDelete: (id: string) => void }) {
  const [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState<Criterion>(c);
  const ok = c.problems.length === 0;
  const Dir = c.direction === "decrease" ? ArrowDownRight : ArrowUpRight;
  const fmt = (v: number | null) => (v === null ? (c.kind === "business" ? "?" : "–") : `${v}`);

  if (edit) {
    const set = (k: keyof Criterion, v: string) =>
      setDraft((d) => ({ ...d, [k]: k === "baseline" || k === "target" ? (v === "" ? null : Number(v)) : v }));
    return (
      <Card testId={`criterion-${c.id}`} className="p-4 ring-2 ring-teal">
        <div className="grid grid-cols-2 gap-2.5">
          {FIELDS.map(([k, label]) => (
            <label key={k} className={k === "metric" || k === "measured_how" ? "col-span-2" : ""}>
              <span className="text-[11px] font-semibold text-ink-3">{label}</span>
              <input data-testid={`edit-${k}`} value={(draft[k] as string | number | null) ?? ""} onChange={(e) => set(k, e.target.value)}
                className="mt-0.5 w-full rounded-md border border-black/10 px-2 py-1.5 text-[12.5px] outline-none focus:border-teal" />
            </label>
          ))}
          <label>
            <span className="text-[11px] font-semibold text-ink-3">Kind</span>
            <select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as Criterion["kind"] })} className="mt-0.5 w-full rounded-md border border-black/10 px-2 py-1.5 text-[12.5px]">
              <option value="business">business</option><option value="quality">quality</option><option value="guardrail">guardrail</option>
            </select>
          </label>
          <label>
            <span className="text-[11px] font-semibold text-ink-3">Better is</span>
            <select value={draft.direction} onChange={(e) => setDraft({ ...draft, direction: e.target.value as Criterion["direction"] })} className="mt-0.5 w-full rounded-md border border-black/10 px-2 py-1.5 text-[12.5px]">
              <option value="decrease">lower</option><option value="increase">higher</option>
            </select>
          </label>
        </div>
        <div className="mt-3 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => { setDraft(c); setEdit(false); }}>Cancel</Button>
          <Button testId="save-criterion" onClick={() => { onSave(draft); setEdit(false); }}>Save</Button>
        </div>
      </Card>
    );
  }

  return (
    <Card testId={`criterion-${c.id}`} className={`p-4 ${ok ? "" : "border-ember/50"}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2"><span className="text-[11px] font-bold text-ink-3">{c.id}</span><Chip tone={KIND_TONE[c.kind]}>{c.kind}</Chip></div>
          <div className="mt-1 text-[14px] font-semibold">{c.name}</div>
          <div className="text-[12.5px] text-ink-2">{c.metric || <i className="text-ink-3">no metric</i>}</div>
        </div>
        <div className="flex gap-1">
          <button aria-label="edit" onClick={() => { setDraft(c); setEdit(true); }} className="rounded-md p-1.5 text-ink-3 hover:bg-mist"><Pencil size={13} /></button>
          <button aria-label="delete" onClick={() => onDelete(c.id)} className="rounded-md p-1.5 text-ink-3 hover:bg-mist"><Trash2 size={13} /></button>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <div className="rounded-lg bg-mist px-3 py-1.5 text-center"><div className="text-[10.5px] text-ink-3">today</div><div className="text-[17px] font-semibold">{fmt(c.baseline)}</div></div>
        <Dir size={18} className={ok ? "text-teal" : "text-ink-3"} />
        <div className={`rounded-lg px-3 py-1.5 text-center ${ok ? "bg-teal-50" : "bg-mist"}`}><div className="text-[10.5px] text-ink-3">target</div><div className={`text-[17px] font-semibold ${ok ? "text-teal" : ""}`}>{fmt(c.target)}</div></div>
        <div className="text-[12px] text-ink-2">{c.unit}</div>
      </div>
      <div className="mt-2 text-[11.5px] text-ink-3"><b className="font-semibold text-ink-2">{c.owner || "no owner"}</b> · {c.by_when || "no deadline"}</div>
      {c.measured_how && <div className="mt-2 text-[11.5px] text-ink-3">Measured: {c.measured_how}</div>}
      {ok ? (
        <div data-testid="measurable" className="mt-3 flex items-center gap-1.5 text-[12px] font-semibold text-teal"><CheckCircle2 size={14} /> Measurable</div>
      ) : (
        <ul data-testid="problems" className="mt-3 space-y-1 rounded-lg bg-ember-50 px-3 py-2">
          {c.problems.map((p) => <li key={p} className="flex items-start gap-1.5 text-[12px] text-ember"><CircleAlert size={13} className="mt-0.5 shrink-0" />{p}</li>)}
        </ul>
      )}
    </Card>
  );
}
