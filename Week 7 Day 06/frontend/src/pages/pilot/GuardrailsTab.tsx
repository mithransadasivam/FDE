// Guardrails: each policy's effect on UC1, measured two ways: the Day 4 evaluation (is it still accurate?)
// and three probe documents (does it stop what it should?).
import { CheckCircle2, Loader2, Play, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type GuardrailPolicy, type RunWithUsage } from "../../api";
import { Button, Card, Chip } from "../../components/ui";

const FIELDS: [string, string][] = [["full_name", "Full name"], ["address", "Address"], ["statement_date", "Statement date"], ["issuer", "Issuer"]];
type Data = { policies: GuardrailPolicy[]; baseline: RunWithUsage[]; active: string };

const pct = (r?: RunWithUsage, f?: string) => (r ? (f ? r.per_field?.[f]?.accuracy : r.overall.accuracy) : undefined);

function Cell({ v, base }: { v?: number; base?: number }) {
  if (v === undefined) return <span className="text-ink-3">—</span>;
  const worse = base !== undefined && v < base - 0.5;
  return <span className={`tabular-nums font-semibold ${worse ? "text-ember" : "text-ink"}`}>{v}%</span>;
}

export default function GuardrailsTab() {
  const [d, setD] = useState<Data | null>(null);
  const [busy, setBusy] = useState("");
  const load = () => api.get<Data>("/api/pilot/guardrails").then(setD);
  useEffect(() => { load(); }, []);
  if (!d) return null;
  const real = (runs: RunWithUsage[]) => runs.filter((r) => r.set === "real" && r.prompt === "extract_v2").at(-1);
  const base = d.baseline.find((r) => r.name === "extract_v2__real") ?? real(d.baseline);
  const act = async (key: string, f: () => Promise<unknown>) => { setBusy(key); try { await f(); await load(); } finally { setBusy(""); } };
  return (
    <div className="space-y-4">
      <Card className="flex items-center justify-between gap-4 px-4 py-3">
        <div>
          <div className="text-[14px] font-semibold">A guardrail is a second set of checks on every model call. It can make UC1 safer, or break it.</div>
          <div className="text-[12.5px] text-ink-2">Each policy is a file in <span className="font-mono">infra/guardrails/</span>: Terraform deploys it, and the console's scripted guardrail imitates it offline. Measure every policy both ways before it goes live.</div>
        </div>
        <div className="shrink-0">
          <Button variant="secondary" disabled={!!busy} testId="eval-none" onClick={() => act("eval-none", () => api.post("/api/eval/runs", { prompt: "extract_v2", set: "real" }))}>
            {busy === "eval-none" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} {base ? "Baseline again" : "Run the baseline"}
          </Button>
        </div>
      </Card>
      <div className="grid grid-cols-2 gap-4">
        {d.policies.map((p) => {
          const run = real(p.runs);
          return (
            <Card key={p.name} className="p-4" testId={`policy-${p.name}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className={`grid h-9 w-9 place-items-center rounded-lg ${p.prompt_attack ? "bg-teal" : "bg-navy"}`}>{p.prompt_attack ? <ShieldCheck size={17} className="text-white" /> : <ShieldAlert size={17} className="text-white" />}</div>
                  <div>
                    <div className="font-mono text-[14px] font-semibold">infra/guardrails/{p.name}.json</div>
                    <div className="text-[12px] text-ink-2">{p.description}</div>
                  </div>
                </div>
              </div>
              <div className="mt-3 space-y-1.5 text-[11.5px]">
                <div className="flex flex-wrap items-center gap-1"><span className="w-[92px] text-ink-3">Prompt attacks</span>{p.prompt_attack ? <Chip tone="teal">blocked on input</Chip> : <Chip tone="ember">not checked</Chip>}</div>
                <div className="flex flex-wrap items-center gap-1"><span className="w-[92px] text-ink-3">Denied topics</span>{p.denied_topics.length ? p.denied_topics.map((t) => <Chip key={t} tone="teal">{t}</Chip>) : <Chip>none</Chip>}</div>
                <div className="flex flex-wrap items-center gap-1"><span className="w-[92px] text-ink-3">Masked</span>{p.masked.map((t) => <Chip key={t} tone={t === "NAME" || t === "ADDRESS" ? "ember" : "mist"}>{t}</Chip>)}</div>
              </div>
              <div className="mt-3 flex gap-2">
                <Button variant="secondary" disabled={!!busy} testId={`eval-${p.name}`}
                  onClick={() => act(`eval-${p.name}`, () => api.post("/api/eval/runs", { prompt: "extract_v2", set: "real", guardrail: p.name }))}>
                  {busy === `eval-${p.name}` ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run the evaluation
                </Button>
                <Button disabled={!!busy} testId={`probe-${p.name}`} onClick={() => act(`probe-${p.name}`, () => api.post(`/api/pilot/guardrails/${p.name}/probes`))}>
                  {busy === `probe-${p.name}` ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run the probes
                </Button>
              </div>
              {(run || p.probes) && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="rounded-lg bg-mist px-3 py-2">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wide text-ink-3">Fields right · 50 cases</div>
                    <div data-testid={`acc-${p.name}`} className={`text-[22px] font-semibold leading-tight ${run && base && run.overall.accuracy < base.overall.accuracy - 0.5 ? "text-ember" : "text-teal"}`}>{run ? `${run.overall.accuracy}%` : "—"}</div>
                    <div className="text-[11px] text-ink-2">{base ? `without a guardrail: ${base.overall.accuracy}%` : "run the baseline first (top right)"}</div>
                  </div>
                  <div className="rounded-lg bg-mist px-3 py-2">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wide text-ink-3">Probes handled</div>
                    <div data-testid={`stopped-${p.name}`} className={`text-[22px] font-semibold leading-tight ${p.probes && p.probes.results.every((r) => r.verdict === "good") ? "text-teal" : "text-ember"}`}>
                      {p.probes ? `${p.probes.results.filter((r) => r.verdict === "good").length} of ${p.probes.results.length}` : "—"}</div>
                    <div className="text-[11px] text-ink-2">{p.probes ? p.probes.label : "not run yet"}</div>
                  </div>
                </div>
              )}
              {p.probes && (
                <div className="mt-3 space-y-1.5" data-testid={`probes-${p.name}`}>
                  {p.probes.results.map((r) => (
                    <div key={r.case_id} data-testid={`probe-${p.name}-${r.case_id}`} data-verdict={r.verdict}
                      className={`flex gap-2 rounded-lg border px-2.5 py-1.5 text-[11.5px] ${r.verdict === "good" ? "border-teal/25 bg-teal-50/60" : "border-ember/30 bg-ember-50"}`}>
                      {r.verdict === "good" ? <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-teal" /> : <XCircle size={14} className="mt-0.5 shrink-0 text-ember" />}
                      <div><span className="font-semibold">{r.title}</span> <span className="font-mono text-ink-3">{r.case_id}</span><div className="text-ink-2">{r.outcome}</div></div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          );
        })}
      </div>
      <Card className="overflow-hidden" testId="guardrail-compare">
        <div className="px-4 pt-3 text-[13.5px] font-semibold">Accuracy by field, with and without each guardrail</div>
        <div className="px-4 text-[12px] text-ink-2">The 50 real cases and the prompt <span className="font-mono">extract_v2</span>. Red: worse than with no guardrail.</div>
        <table className="mt-2 w-full text-left text-[12.5px]">
          <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
            <tr><th className="px-4 py-1.5">Guardrail</th><th className="py-1.5">All fields</th>{FIELDS.map(([, l]) => <th key={l} className="py-1.5">{l}</th>)}</tr>
          </thead>
          <tbody>
            <tr className="border-t border-black/[0.05]"><td className="px-4 py-2 font-semibold">None (Day 4)</td><td className="py-2"><Cell v={pct(base)} /></td>{FIELDS.map(([f]) => <td key={f} className="py-2"><Cell v={pct(base, f)} /></td>)}</tr>
            {d.policies.map((p) => {
              const r = real(p.runs);
              return (
                <tr key={p.name} data-testid={`row-${p.name}`} className="border-t border-black/[0.05]">
                  <td className="px-4 py-2 font-mono font-semibold">{p.name}</td><td className="py-2"><Cell v={pct(r)} base={pct(base)} /></td>
                  {FIELDS.map(([f]) => <td key={f} className="py-2"><Cell v={pct(r, f)} base={pct(base, f)} /></td>)}
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
