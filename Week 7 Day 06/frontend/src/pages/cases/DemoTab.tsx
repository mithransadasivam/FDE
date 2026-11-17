// The demo against the success criteria agreed on Day 1: run the prototype on Tom's 30 labelled documents.
import { CheckCircle2, CircleDashed, Clock, FlaskConical, Loader2, Play, XCircle } from "lucide-react";
import { useState } from "react";
import { api, ApiError, type DemoResult } from "../../api";
import { Button, Card, Chip, Kpi, NotBuilt } from "../../components/ui";

const STATUS = {
  on_track: { tone: "teal", text: "On track", I: CheckCircle2 },
  off_track: { tone: "ember", text: "Off track", I: XCircle },
  pending: { tone: "amber", text: "Not yet", I: CircleDashed },
  pilot: { tone: "mist", text: "Measured in the pilot", I: Clock },
} as const;

export default function DemoTab() {
  const [r, setR] = useState<DemoResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [nb, setNb] = useState("");
  const run = async () => {
    setBusy(true); setNb("");
    try { setR(await api.get<DemoResult>("/api/cases/demo")); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; }
    finally { setBusy(false); }
  };
  return (
    <div>
      <Card className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-mist"><FlaskConical size={17} className="text-ink-2" /></div>
          <div>
            <div className="text-[14px] font-semibold">Tom's 30 checked documents</div>
            <div className="text-[12.5px] text-ink-2">data/Day03_Slide26_tom_labels.csv · the right value for every field, and Tom's own decision</div>
          </div>
        </div>
        <Button onClick={run} disabled={busy} testId="run-demo">{busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} {r ? "Run again" : "Run the prototype on all 30"}</Button>
      </Card>
      {nb && <div className="mt-3"><NotBuilt ticket={nb.includes("ENG-302") ? "ENG-302" : "ENG-301"}>{nb}</NotBuilt></div>}
      {r && (
        <>
          <div className="mt-4 grid grid-cols-4 gap-3" data-testid="demo-kpis">
            <Kpi label="Fields right" value={<span data-testid="accuracy">{r.accuracy}%</span>} tone={r.accuracy >= 90 ? "teal" : "ember"} sub={`${r.correct} of ${r.fields} fields match Tom's labels`} />
            <Kpi label="Wrong fields shown to a person" value={`${r.caught} of ${r.wrong.length}`} tone={r.caught === r.wrong.length ? "teal" : "amber"} sub="boxed amber or red, or not on the page" />
            <Kpi label="Rules agree with Tom" value={<span data-testid="agree">{r.rules.agree} of {r.rules.compared}</span>} tone={r.rules.agree === r.rules.compared ? "teal" : "amber"} sub={`${r.rules.sent_to_person} more sent to a person to confirm a field`} />
            <Kpi label="Date rule counts from" value={<span className="text-[17px]">{r.rules.date_counted_from.replace("_", " ")}</span>} sub="engagement/poa_rules.json" />
          </div>
          <Card className="mt-4 overflow-hidden" testId="criteria">
            <div className="px-4 pt-3 text-[13px] font-semibold">Against the success criteria agreed in discovery</div>
            <table className="mt-2 w-full text-[13px]">
              <thead className="bg-mist text-left text-[11px] uppercase tracking-wide text-ink-3">
                <tr><th className="px-4 py-2">Criterion</th><th>Target</th><th>What the prototype can measure</th><th>Result</th><th>Status</th></tr>
              </thead>
              <tbody>
                {r.criteria.map((c) => {
                  const s = STATUS[c.status];
                  return (
                    <tr key={c.id} data-testid={`crit-${c.id}`} data-status={c.status} className="border-t border-black/[0.05] align-top">
                      <td className="px-4 py-2.5"><span className="font-mono text-[11.5px] text-ink-3">{c.id}</span> <span className="font-semibold">{c.name}</span></td>
                      <td className="py-2.5 tabular-nums">{c.target} {c.unit}</td>
                      <td className="py-2.5 pr-4"><div>{c.measure}</div><div className="text-[12px] text-ink-2">{c.note}</div></td>
                      <td className="py-2.5 font-semibold tabular-nums">{c.value === null ? "—" : `${c.value}%`}</td>
                      <td className="py-2.5 pr-4"><Chip tone={s.tone}><s.I size={12} /> {s.text}</Chip></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <Card className="p-4" testId="wrong">
              <div className="text-[13px] font-semibold">Every wrong field, and whether a person would see it</div>
              {r.wrong.map((w) => (
                <div key={w.case_id + w.field} className="mt-2.5 flex items-start gap-2.5 text-[12.5px]">
                  {w.flagged ? <CheckCircle2 size={15} className="mt-[1px] shrink-0 text-teal" /> : <XCircle size={15} className="mt-[1px] shrink-0 text-ember" />}
                  <div><span className="font-mono text-ink-3">{w.case_id}</span> <span className="font-semibold">{w.label}</span>: read <b>{w.got}</b>, Tom says <b>{w.expected}</b>
                    <div className="text-ink-2">{w.flagged ? `Shown to a person (${w.status.replace(/_/g, " ")})` : `Not flagged: confidence ${w.confidence.toFixed(2)}, and it still passes the rules`}</div></div>
                </div>
              ))}
            </Card>
            <Card className="p-4" testId="disagreements">
              <div className="text-[13px] font-semibold">Where the rules and Tom disagree</div>
              {r.rules.disagreements.length === 0 && <div className="mt-2.5 text-[12.5px] text-teal">None: the rules agree with every decision Tom made.</div>}
              {r.rules.disagreements.map((d) => (
                <div key={d.case_id} className="mt-2.5 text-[12.5px]">
                  <span className="font-mono text-ink-3">{d.case_id}</span> <span className="font-semibold">{d.check}</span>: {d.detail}
                  <div className="text-ink-2">Tom: {d.tom.replace("_", " ")}{d.tom_note && ` · “${d.tom_note}”`}</div>
                </div>
              ))}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
