// Teacher and student (Activity 1, ticket ENG-1101): the pilot's reads are the training data; train the small model
// and score it alone on the October batch, against Tom's keyed labels.
import { GraduationCap, Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type ReadSample, type SmallEval, type SmallModelMeta } from "../../api";
import { Button, Card, Chip, Kpi } from "../../components/ui";
import { Bar, FIELD_NAMES, KIND_NAMES, TicketChips11, pct, useDistil } from "./parts";

export default function TrainTab() {
  const { st, reload } = useDistil();
  const [files, setFiles] = useState<string[]>(["pilot"]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [last, setLast] = useState<SmallModelMeta | null>(null);
  const [ev, setEv] = useState<SmallEval | null>(null);
  const [sample, setSample] = useState<ReadSample[] | null>(null);
  const [weights, setWeights] = useState<{ feature: string; weight: number }[]>([]);
  const active = st?.active ?? null;
  useEffect(() => {
    if (!active) return;
    api.get<SmallEval>(`/api/distil/evaluate?set=october&model=${active}`).then(setEv);
    api.get<{ weights: { feature: string; weight: number }[] }>(`/api/distil/weights?label=statement_date&model=${active}`).then((w) => setWeights(w.weights));
  }, [active]);
  useEffect(() => { api.get<{ sample: ReadSample[] }>("/api/distil/reads/pilot?only_disagree=true&n=6").then((r) => setSample(r.sample)); }, []);
  if (!st) return null;
  const pilot = st.read_files.find((r) => r.name === "pilot")!;
  const train = async () => {
    setBusy(true); setErr("");
    try { setLast(await api.post<SmallModelMeta>("/api/distil/train", { read_files: files })); await reload(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const toggle = (n: string) => setFiles(files.includes(n) ? files.filter((f) => f !== n) : [...files, n]);
  return (
    <div className="space-y-4">
      <TicketChips11 st={st} />
      <div className="grid grid-cols-[1fr_1.15fr] gap-4">
        <div className="space-y-4">
          <Card className="p-4" testId="teacher-reads">
            <div className="flex items-center gap-2"><GraduationCap size={16} className="text-navy" /><span className="text-[13.5px] font-semibold">The teacher's reads</span>
              <span className="ml-auto font-mono text-[11px] text-ink-3">data/{pilot.file}</span></div>
            <div className="mt-1 text-[12px] text-ink-2">Since ADR-003 the pilot has read every document twice with Sonnet 5. Nobody keyed these documents: the only check is whether the two readings agree.</div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <Kpi label="Reads" value={pilot.reads.toLocaleString()} sub={pilot.months.join(", ")} />
              <Kpi label="Both readings agree" value={<span data-testid="reads-agree">{pilot.all_agree.toLocaleString()}</span>} sub={`${(100 * pilot.all_agree / pilot.reads).toFixed(0)}% of the reads`} tone="teal" />
              <Kpi label="They disagree" value={(pilot.reads - pilot.all_agree).toLocaleString()} sub="at least one reading is wrong" tone="amber" />
            </div>
            <div className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-ink-3">Disagreements, by field</div>
            <div className="mt-1 grid grid-cols-4 gap-2 text-[12px]">
              {Object.entries(pilot.disagree_by_field).map(([f, n]) => <div key={f} className="rounded-lg bg-mist px-2 py-1.5"><div className="text-ink-3">{FIELD_NAMES[f]}</div><div className="font-semibold">{n}</div></div>)}
            </div>
            {sample && (
              <table className="mt-3 w-full text-[11.5px]" data-testid="disagree-sample">
                <thead className="text-left text-[10px] uppercase tracking-wide text-ink-3"><tr><th className="py-1">Read</th><th>Field</th><th>Parser reading</th><th>Vision reading</th></tr></thead>
                <tbody>{sample.map((r) => r.disagree.slice(0, 1).map((f) => (
                  <tr key={r.doc_id + f} className="border-t border-black/[0.05]"><td className="whitespace-nowrap py-1 pr-2 font-mono">{r.doc_id}</td><td>{FIELD_NAMES[f]}</td>
                    <td className="font-mono">{r.parser[f]}</td><td className="font-mono">{r.vision[f]}</td></tr>)))}</tbody>
              </table>
            )}
          </Card>
          <Card className="p-4" testId="train-card">
            <div className="text-[13.5px] font-semibold">Train the small model</div>
            <div className="mt-1 text-[12px] text-ink-2">A logistic regression over each word's features (backend/app/distil/features.py), on your laptop's CPU. word_labels() (ENG-1101) decides which reads it learns from.</div>
            <div className="mt-3 space-y-1.5">
              {st.read_files.map((r) => (
                <label key={r.name} className="flex items-center gap-2 text-[12.5px]">
                  <input type="checkbox" data-testid={`reads-${r.name}`} checked={files.includes(r.name)} onChange={() => toggle(r.name)} />
                  <span className="font-semibold">{r.name}</span><span className="text-ink-3">{r.reads.toLocaleString()} reads · {Object.keys(r.kinds).map((k) => KIND_NAMES[k] ?? k).join(", ")}</span>
                </label>
              ))}
            </div>
            <div className="mt-3 flex items-center gap-3">
              <Button testId="train" onClick={train} disabled={busy || !files.length}>{busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Train</Button>
              {last && <span className="text-[12px] text-ink-2" data-testid="trained">Trained <b className="font-mono">{last.name}</b>: kept <b data-testid="kept">{last.kept.toLocaleString()}</b> reads, left out <b data-testid="skipped">{last.skipped}</b>, in {last.train_seconds} s</span>}
            </div>
            {err && <div className="mt-2 rounded-lg bg-ember-50 px-3 py-2 text-[12px]">{err}</div>}
          </Card>
        </div>
        <div className="space-y-4">
          <Card className="overflow-hidden" testId="models">
            <div className="px-4 py-2.5 text-[13.5px] font-semibold">Models</div>
            <table className="w-full text-[12px]">
              <thead className="bg-mist text-left text-[10px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Model</th><th>Trained on</th><th className="text-right">Reads kept</th><th className="text-right">Size</th><th className="text-right">Train</th><th className="px-4 text-right">October, alone</th></tr></thead>
              <tbody>
                {st.models.map((m) => (
                  <tr key={m.name} data-testid={`model-${m.name}`} className={`border-t border-black/[0.05] ${m.name === active ? "bg-teal-50/60" : ""}`}>
                    <td className="px-4 py-1.5 font-mono font-semibold">{m.name} {m.name === active && <Chip tone="teal">in use</Chip>}</td>
                    <td>{m.read_files.join(" + ")}</td><td className="text-right">{m.kept.toLocaleString()} of {m.reads.toLocaleString()}</td>
                    <td className="text-right">{m.size_kb} KB</td><td className="text-right">{m.train_seconds} s</td>
                    <td className="px-4 text-right font-semibold" data-testid={`acc-${m.name}`}>{pct(m.october)}</td>
                  </tr>
                ))}
                {!st.models.length && <tr><td colSpan={6} className="px-4 py-3 text-ink-3">No model yet: press Train.</td></tr>}
              </tbody>
            </table>
          </Card>
          {ev && ev.model && (
            <Card className="p-4" testId="october-alone">
              <div className="flex items-baseline gap-2"><span className="text-[13.5px] font-semibold">{ev.model} alone on the October batch</span>
                <span className="text-[12px] text-ink-3">200 documents, against Tom's keyed labels</span>
                <span className="ml-auto text-[22px] font-semibold" data-testid="oct-acc">{pct(ev.overall)}</span></div>
              <div className="mt-3 space-y-2">
                {Object.entries(ev.per_field).map(([f, a]) => (
                  <div key={f} className="grid grid-cols-[120px_1fr_60px] items-center gap-3 text-[12.5px]" data-testid={`field-acc-${f}`}>
                    <span>{FIELD_NAMES[f]}</span><Bar value={a.accuracy ?? 0} tone={(a.accuracy ?? 0) < 95 ? "ember" : "teal"} /><span className="text-right font-semibold">{pct(a)}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 text-[12px] text-ink-2">One keyer at the bank: 98.6% · the pilot's parser reading alone (extract_v2): 95.9% · {ev.ms_per_doc} ms a document on this laptop</div>
              {weights.length > 0 && (
                <div className="mt-3 border-t border-black/[0.05] pt-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">What counts most towards statement_date</div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5" data-testid="weights">
                    {weights.slice(0, 10).map((w) => <span key={w.feature} className="rounded-md bg-mist px-1.5 py-0.5 font-mono text-[11px]">{w.feature} <b className="text-teal">+{w.weight}</b></span>)}
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
