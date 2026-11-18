// Compare: the same 200 documents read two ways, scored against the bank's double-keyed answers.
import { Eye, Loader2, Play, ScanText, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Comparison, type RunScore6, type BatchRun } from "../../api";
import { Button, Card, Chip, NotBuilt } from "../../components/ui";

const SLICES = [
  ["bill", "Utility bills"], ["statement", "Bank statements"], ["digital", "Digital PDFs"], ["scan", "Scans"],
  ["smudge", "Smudged scans"], ["two_dates", "Bills with two dates"], ["joint_names", "Joint names"],
] as const;
const FIELD_LABEL: Record<string, string> = { full_name: "Full name", address: "Address", statement_date: "Statement date", issuer: "Issuer" };
const pct = (v?: number) => (v == null ? "—" : `${v.toFixed(1)}%`);

export default function CompareTab({ set }: { set: string }) {
  const [c, setC] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState("");
  const [nb, setNb] = useState("");
  const [last, setLast] = useState<BatchRun | null>(null);
  const [sel, setSel] = useState("");
  const load = () => api.get<Comparison>(`/api/pipeline/compare?set=${set}`).then((x) => { setC(x); if (!sel && x.runs[0]) setSel(x.runs[0].prompt); });
  useEffect(() => { setSel(""); load(); }, [set]);
  if (!c) return null;
  const run = async (prompt: string) => {
    setBusy(prompt); setNb("");
    try { setLast(await api.post<BatchRun>("/api/pipeline/run", { set, prompts: [prompt], concurrency: 8 })); setSel(prompt); await load(); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; }
    finally { setBusy(""); }
  };
  const byPrompt = Object.fromEntries(c.runs.map((r) => [r.prompt, r]));
  const chosen: RunScore6 | undefined = byPrompt[sel];
  const all = [...c.prompts.parser.map((p) => ["parser", p] as const), ...c.prompts.vision.map((p) => ["vision", p] as const)];
  const h = c.human;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[1fr_1.6fr] gap-4">
        <Card className="p-4" testId="human-bar">
          <div className="flex items-center gap-2 text-[13.5px] font-semibold"><Users size={15} /> The bar: how well the bank keys them today</div>
          <div className="mt-0.5 text-[12px] text-ink-2">Two analysts keyed every document. Where they differed, Tom settled it: that is the label.</div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg bg-mist px-2 py-2"><div className="text-[20px] font-semibold">{pct(h.one_keyer)}</div><div className="text-[11px] text-ink-2">one keyer</div></div>
            <div className="rounded-lg bg-mist px-2 py-2"><div className="text-[20px] font-semibold">{pct(h.agreement)}</div><div className="text-[11px] text-ink-2">the two agree</div></div>
            <div className="rounded-lg bg-mist px-2 py-2"><div className="text-[20px] font-semibold">{h.settled_by_tom}</div><div className="text-[11px] text-ink-2">settled by Tom</div></div>
          </div>
          <div className="mt-2.5 text-[11.5px] text-ink-3">Keyer A {pct(h.keyer_a)} · keyer B {pct(h.keyer_b)} of {h.fields} fields. The pipeline has to beat one keyer, not be perfect.</div>
        </Card>
        <Card className="p-4" testId="run-controls">
          <div className="text-[13.5px] font-semibold">Read the 200 with a prompt</div>
          <div className="text-[12px] text-ink-2">
            Parser + LLM sends the parsed words with their ids; the vision model gets a picture of the page. A run reads 8 documents at a time.
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {all.map(([m, p]) => (
              <div key={p} className="flex items-center justify-between rounded-lg border border-black/[0.06] px-3 py-2">
                <div className="flex items-center gap-2 text-[12.5px]">
                  {m === "parser" ? <ScanText size={14} className="text-navy" /> : <Eye size={14} className="text-ember" />}
                  <span className="font-mono font-semibold">{p}</span>
                  {byPrompt[p] && <Chip tone="teal">{pct(byPrompt[p].overall.accuracy)}</Chip>}
                </div>
                <Button variant="secondary" onClick={() => run(p)} disabled={!!busy} testId={`run-${p}`}>
                  {busy === p ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} {byPrompt[p] ? "Run again" : "Run"}
                </Button>
              </div>
            ))}
          </div>
          {last && <div className="mt-2 text-[11.5px] text-ink-3" data-testid="last-run">Last run: {last.done} of {last.calls} calls, {(last.wall_ms / 1000).toFixed(0)} s{last.simulated ? " (simulated time, scripted model)" : ""}.</div>}
        </Card>
      </div>
      {nb && <NotBuilt ticket="ENG-601">{nb}. Every run parses the documents first: open docs/tickets/ENG-601.md.</NotBuilt>}

      <Card className="overflow-hidden" testId="compare-table">
        <div className="px-4 py-3 text-[13.5px] font-semibold">Each run against the bank's answers, field by field</div>
        <table className="w-full text-left text-[12.5px]">
          <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
            <tr><th className="px-4 py-1.5">Method</th><th>Prompt</th><th className="text-right">Fields right</th>
              {Object.keys(FIELD_LABEL).map((f) => <th key={f} className="text-right">{FIELD_LABEL[f]}</th>)}
              <th className="text-right">Found on the page</th><th className="text-right">Tokens in / out</th><th className="text-right">Time</th><th className="pr-4 text-right">USD per doc</th></tr>
          </thead>
          <tbody>
            <tr className="border-t border-black/[0.05] bg-mist/40 text-ink-2"><td className="px-4 py-2" colSpan={2}>One keyer at the bank, today</td>
              <td className="text-right font-semibold">{pct(h.one_keyer)}</td><td colSpan={8} /></tr>
            {c.runs.map((r) => (
              <tr key={r.prompt} data-testid={`cmp-${r.prompt}`} onClick={() => setSel(r.prompt)}
                className={`cursor-pointer border-t border-black/[0.05] ${sel === r.prompt ? "bg-amber-50/60" : ""}`}>
                <td className="px-4 py-2 font-semibold">{r.method === "parser" ? "Parser + LLM" : "Vision model"}</td>
                <td className="font-mono text-[11.5px]">{r.prompt}</td>
                <td className={`text-right font-semibold ${r.overall.accuracy >= h.one_keyer ? "text-teal" : r.overall.accuracy >= 90 ? "text-amber" : "text-ember"}`}>{pct(r.overall.accuracy)}</td>
                {Object.keys(FIELD_LABEL).map((f) => <td key={f} className={`text-right tabular-nums ${r.per_field[f]?.accuracy < 90 ? "font-semibold text-ember" : ""}`}>{pct(r.per_field[f]?.accuracy)}</td>)}
                <td className={`text-right tabular-nums ${r.grounded < 95 ? "font-semibold text-ember" : ""}`}>{pct(r.grounded)}</td>
                <td className="text-right tabular-nums">{r.tokens.input.toLocaleString()} / {r.tokens.output}</td>
                <td className="text-right tabular-nums">{(r.latency_ms / 1000).toFixed(1)} s</td>
                <td className="pr-4 text-right tabular-nums">{r.usd_per_doc != null ? r.usd_per_doc.toFixed(5) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-black/[0.05] px-4 py-2 text-[11.5px] text-ink-3">
          “Found on the page”: the share of values that are printed on the page as given (the parser cites words; the vision model's values are looked up afterwards).
          {c.runs.some((r) => r.scripted) && " Tokens and time come from the scripted model; prices are the class model's (Day06_Slide15_model_prices.csv)."}
        </div>
      </Card>

      {chosen && (
        <div className="grid grid-cols-[1fr_1.15fr] gap-4">
          <Card className="overflow-hidden" testId="slice-table">
            <div className="px-4 py-3 text-[13.5px] font-semibold">Where each run goes wrong: fields right, by slice</div>
            <table className="w-full text-left text-[12.5px]">
              <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
                <tr><th className="px-4 py-1.5">Slice</th>{c.runs.map((r) => <th key={r.prompt} className="pr-3 text-right font-mono normal-case">{r.prompt}</th>)}</tr>
              </thead>
              <tbody>
                {SLICES.map(([k, label]) => (
                  <tr key={k} className="border-t border-black/[0.05]" data-testid={`slice-${k}`}>
                    <td className="px-4 py-1.5">{label} <span className="text-[11px] text-ink-3">({(c.runs[0]?.per_slice[k]?.total ?? 0) / 4} docs)</span></td>
                    {c.runs.map((r) => {
                      const v = r.per_slice[k]?.accuracy;
                      return <td key={r.prompt} className={`pr-3 text-right tabular-nums ${v != null && v < 90 ? "font-semibold text-ember" : ""}`}>{pct(v)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card className="overflow-hidden" testId="errors">
            <div className="px-4 py-3">
              <div className="text-[13.5px] font-semibold">What <span className="font-mono">{chosen.prompt}</span> got wrong: {chosen.overall.total - chosen.overall.correct} fields</div>
              <div className="text-[12px] text-ink-2">Click a run in the table above to see its errors.</div>
            </div>
            <div className="max-h-[300px] overflow-auto">
              <table className="w-full text-left text-[12px]">
                <thead className="sticky top-0 bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Doc</th><th>Field</th><th>Read</th><th className="pr-4">The bank's answer</th></tr></thead>
                <tbody>
                  {chosen.errors.slice(0, 40).map((e, i) => (
                    <tr key={i} className="border-t border-black/[0.05]">
                      <td className="px-4 py-1.5 font-mono">{e.doc_id}</td><td>{FIELD_LABEL[e.field]}</td>
                      <td className="font-semibold text-ember">{e.got || "—"}</td><td className="pr-4">{e.expected}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
