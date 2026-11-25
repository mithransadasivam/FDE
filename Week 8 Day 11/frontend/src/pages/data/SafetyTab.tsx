// Safety: queries a model might write, good and bad, through the validator (ENG-701) and the cost check.
import { Ban, CheckCircle2, Loader2, ShieldAlert, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type ProbeView } from "../../api";
import { Button, Card, Chip, Kpi, NotBuilt } from "../../components/ui";

export default function SafetyTab() {
  const [p, setP] = useState<ProbeView | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => { setBusy(true); api.get<ProbeView>("/api/data/probes").then(setP).finally(() => setBusy(false)); };
  useEffect(load, []);
  if (!p) return null;
  const s = p.summary;
  return (
    <div className="space-y-4">
      {p.not_built && <NotBuilt ticket="ENG-701">{p.not_built}. Until the validator is built, no query runs anywhere in the console: open docs/tickets/ENG-701.md.</NotBuilt>}
      {s && (
        <div className="grid grid-cols-4 gap-3" data-testid="safety-summary">
          <Kpi label="Harmful queries refused" value={`${s.refused} of ${s.should_refuse}`} tone={s.refused === s.should_refuse ? "teal" : "ember"} sub="changes, files, other tables, two statements" />
          <Kpi label="Safe queries allowed" value={`${s.allowed} of ${s.should_allow}`} tone={s.allowed === s.should_allow ? "teal" : "ember"} sub="with a row limit added" />
          <Kpi label="Stopped by the cost check" value={s.by_cost_check} sub="after the validator, before it runs" />
          <Kpi label="As expected" value={`${s.passed} of ${s.total}`} tone={s.passed === s.total ? "teal" : "amber"} />
        </div>
      )}
      <Card className="overflow-hidden" testId="probe-table">
        <div className="flex items-center justify-between px-4 py-3">
          <div>
            <div className="flex items-center gap-2 text-[13.5px] font-semibold"><ShieldAlert size={15} /> {p.probes.length} queries a model might write</div>
            <div className="text-[12px] text-ink-2">From data/Day07_Slide10_safety_probes.json. The model is not involved: each query goes straight to the checks.</div>
          </div>
          <Button variant="secondary" onClick={load} disabled={busy} testId="probes-run">{busy && <Loader2 size={13} className="animate-spin" />} Check again</Button>
        </div>
        <table className="w-full text-left text-[12.5px]">
          <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
            <tr><th className="px-4 py-1.5">#</th><th>The query</th><th>Why it is here</th><th>Expected</th><th>Result</th><th className="pr-4">Reason, or what changed</th></tr>
          </thead>
          <tbody>
            {p.probes.map((x) => (
              <tr key={x.id} data-testid={`probe-${x.id}`} className="border-t border-black/[0.05] align-top">
                <td className="px-4 py-2 text-ink-3">{x.id}</td>
                <td className="max-w-[360px] py-2 pr-3 font-mono text-[11.5px]">{x.sql}</td>
                <td className="py-2 pr-3 text-ink-2">{x.why}</td>
                <td className="py-2 pr-3">{x.expect === "refuse" ? <Chip tone="mist">refuse</Chip> : <Chip tone="mist">allow</Chip>}</td>
                <td className="py-2 pr-3">
                  {x.verdict === null ? <span className="text-ink-3">—</span> : x.verdict === "refuse"
                    ? <Chip tone={x.passed ? "teal" : "ember"}><Ban size={11} /> {x.stage === "cost" ? "cost check" : "refused"}</Chip>
                    : <Chip tone={x.passed ? "teal" : "ember"}><CheckCircle2 size={11} /> ran{x.rows != null ? `: ${x.rows.toLocaleString()} rows` : ""}</Chip>}
                  {x.passed === false && <XCircle size={13} className="ml-1 inline text-ember" />}
                </td>
                <td className="py-2 pr-4 text-[11.5px] text-ink-2">{[...(x.reasons ?? []), ...(x.notes ?? [])].join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
