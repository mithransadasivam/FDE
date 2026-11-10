import { CheckCircle2, CircleAlert, CircleHelp, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type CostResult, type Option, type Rule } from "../../api";
import ArchCanvas from "../../components/ArchCanvas";
import { Card, Chip, NotBuilt } from "../../components/ui";

export default function ArchitectureTab() {
  const [opts, setOpts] = useState<Option[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [sel, setSel] = useState("A");
  const [cost, setCost] = useState<CostResult | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get<{ rules: Rule[]; options: Option[] }>("/api/design/options").then((r) => { setOpts(r.options); setRules(r.rules); }).catch((e) => setError(e.message));
    api.get<CostResult>("/api/design/cost").then(setCost).catch(() => null);
  }, []);
  const opt = opts.find((o) => o.id === sel) ?? opts[0];
  const notChecked = opts.some((o) => o.violations === null);
  const broke = (o: Option, rule: string) => (o.violations ?? []).some((v) => v.rule === rule);
  const costOf = (id: string) => cost?.options.find((c) => c.id === id)?.total_gbp;

  if (error) return <div className="rounded-lg bg-ember-50 px-4 py-3 text-[12.5px] text-ember">{error}</div>;
  if (!opt) return null;
  return (
    <div>
      {notChecked && <div className="mb-3"><NotBuilt ticket="ENG-202">The options are drawn, but nothing checks them against the client's rules yet. Open docs/tickets/ENG-202.md.</NotBuilt></div>}
      <div className="grid grid-cols-[1fr_360px] gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              {opts.map((o) => (
                <button key={o.id} data-testid={`opt-${o.id}`} onClick={() => setSel(o.id)}
                  className={`rounded-lg border px-3 py-1.5 text-[12.5px] font-semibold ${o.id === opt.id ? "border-navy bg-navy text-white" : "border-black/10 bg-white text-ink-2"}`}>
                  Option {o.id} · {o.name}
                </button>
              ))}
              {!opts.some((o) => o.id === "B") && <span className="rounded-lg border border-dashed border-amber px-3 py-1.5 text-[12px] text-amber">Option B: write docs/architecture/option_b.json</span>}
            </div>
            <div className="flex gap-3 text-[10.5px] text-ink-3">
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-[#5B6BBF]" />model</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-[#30365E]" />OCR</span>
              <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm border border-ember" />decision</span>
            </div>
          </div>
          <div className="mt-2 text-[12.5px] text-ink-2">{opt.summary}</div>
          <div className="mt-2"><ArchCanvas option={opt} /></div>
        </Card>
        <div className="space-y-3">
          <Card className="p-4" testId="rule-check">
            <div className="text-[14px] font-semibold">Client rules: Option {opt.id}</div>
            <div className="mt-2 space-y-1.5">
              {rules.map((r) => {
                const ok = opt.violations !== null && !broke(opt, r.rule);
                const Icon = opt.violations === null ? CircleHelp : ok ? CheckCircle2 : XCircle;
                return (
                  <div key={r.rule} data-testid={`rule-${r.rule}`} data-ok={String(ok)} className="flex items-start gap-2 text-[12.5px]">
                    <Icon size={15} className={`mt-0.5 shrink-0 ${opt.violations === null ? "text-ink-3" : ok ? "text-teal" : "text-ember"}`} />
                    <span className="flex-1">{r.text}</span><span className="text-[11px] text-ink-3">{r.source}</span>
                  </div>
                );
              })}
            </div>
            {opt.violations && opt.violations.length === 0 && <div data-testid="all-rules-met" className="mt-3 rounded-lg bg-teal-50 px-3 py-2 text-[12.5px] font-semibold text-teal">Meets all {rules.length} client rules</div>}
            {opt.violations && opt.violations.length > 0 && (
              <ul data-testid="violations" className="mt-3 space-y-1 rounded-lg bg-ember-50 px-3 py-2">
                {opt.violations.map((v, i) => <li key={i} className="flex items-start gap-1.5 text-[12px] text-ember"><CircleAlert size={13} className="mt-0.5 shrink-0" />{v.message}</li>)}
              </ul>
            )}
          </Card>
          <Card className="p-4">
            <div className="text-[13px] font-semibold">Strengths</div>
            <ul className="mt-1 list-disc pl-4 text-[12px] text-ink-2">{opt.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
            <div className="mt-2 text-[13px] font-semibold">Weaknesses</div>
            <ul className="mt-1 list-disc pl-4 text-[12px] text-ink-2">{opt.weaknesses.map((s) => <li key={s}>{s}</li>)}</ul>
          </Card>
        </div>
      </div>
      <Card className="mt-4 overflow-hidden" testId="comparison">
        <table className="w-full text-left text-[12.5px]">
          <thead className="bg-navy text-[11.5px] text-white"><tr><th className="px-4 py-2">Option</th><th className="px-3">Client rules</th><th className="px-3">Time to pilot</th><th className="px-3">Run-cost / month</th><th className="px-3">Main weakness</th></tr></thead>
          <tbody>
            {opts.map((o, i) => {
              const n = o.violations?.length;
              return (
                <tr key={o.id} className={i % 2 ? "bg-mist/50" : ""}>
                  <td className="px-4 py-2 font-semibold">Option {o.id} · {o.name}</td>
                  <td className="px-3">{n === undefined || n === null ? <Chip>not checked</Chip> : n === 0 ? <Chip tone="teal">all met</Chip> : <Chip tone="ember">{n} broken</Chip>}</td>
                  <td className="px-3 tabular-nums">{o.time_to_pilot_weeks} {o.time_to_pilot_weeks === 1 ? "week" : "weeks"}</td>
                  <td className="px-3 tabular-nums">{costOf(o.id) !== undefined ? `£${costOf(o.id)!.toFixed(0)}` : "–"}</td>
                  <td className="px-3 text-ink-2">{o.weaknesses[0]}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
