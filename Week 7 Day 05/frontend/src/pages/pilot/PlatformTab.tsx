// Platform: which model the console calls, where that call is processed, and an offline check of the Bedrock client.
import { CheckCircle2, CircleAlert, Cloud, FlaskConical, Loader2, MapPin, Play, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type PilotStatus, type SelfTest, type TryResult } from "../../api";
import { Button, Card, Chip, NotBuilt } from "../../components/ui";
import { STATUS_STYLE } from "../../components/fieldStyle";

const ROUTING: Record<string, string> = { "in-region": "In-Region", geo: "Geographic", global: "Global" };
const CASES = ["D03-001", "D03-007", "D03-014", "D04-031", "D04-043"];

function Json({ value }: { value: unknown }) {
  const text = JSON.stringify(value, null, 2);
  return (
    <pre data-testid="request" className="max-h-[430px] overflow-auto whitespace-pre-wrap break-all rounded-lg bg-navy px-3 py-2.5 font-mono text-[11px] leading-[1.5] text-white/85">
      {text.split("\n").map((line, i) => {
        const hot = /"(modelId|guardrailIdentifier|guardrailVersion|temperature)"/.test(line);
        return <div key={i} className={hot ? "-mx-3 bg-white/10 px-3 text-[#5FD3C1]" : ""}>{line}</div>;
      })}
    </pre>
  );
}

export default function PlatformTab() {
  const [s, setS] = useState<PilotStatus | null>(null);
  const [test, setTest] = useState<SelfTest | null>(null);
  const [tried, setTried] = useState<TryResult | null>(null);
  const [nb, setNb] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [cid, setCid] = useState(CASES[0]);
  useEffect(() => { api.get<PilotStatus>("/api/pilot/status").then(setS); }, []);
  if (!s) return null;
  const r = s.residency;
  const run = async () => {
    setBusy("test"); setNb("");
    try { setTest(await api.post<SelfTest>("/api/pilot/selftest", { case_id: "D03-001" })); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNb(e.message); else throw e; }
    finally { setBusy(""); }
  };
  const tryCase = async () => {
    setBusy("try"); setErr("");
    try { setTried(await api.post<TryResult>("/api/pilot/try", { case_id: cid })); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(""); }
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[1.05fr_1fr] gap-4">
        <Card className="p-5" testId="where">
          <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-ink-3"><Cloud size={14} /> Where the model runs now</div>
          <div className="mt-2 font-mono text-[15px] font-semibold" data-testid="model-id">{r.model_id}</div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px] text-ink-2">
            <Chip tone="navy">{s.settings.provider === "bedrock" && !s.settings.fake ? "Amazon Bedrock" : s.settings.fake ? "Scripted model" : "OpenRouter"}</Chip>
            <Chip>Region {r.region}</Chip>
            <Chip tone={r.routing === "in-region" ? "teal" : "amber"}>{ROUTING[r.routing]} routing</Chip>
            {r.model && <Chip>{r.model}</Chip>}
          </div>
          <div className={`mt-4 flex gap-3 rounded-xl p-3.5 ${r.stays_in_uk ? "bg-teal-50" : "bg-ember-50"}`} data-testid="residency" data-ok={r.stays_in_uk}>
            {r.stays_in_uk ? <CheckCircle2 size={22} className="mt-0.5 shrink-0 text-teal" /> : <XCircle size={22} className="mt-0.5 shrink-0 text-ember" />}
            <div>
              <div className={`text-[15px] font-semibold ${r.stays_in_uk ? "text-teal" : "text-ember"}`}>{r.stays_in_uk ? "Customer data stays in the UK" : "Customer data leaves the UK"}</div>
              <div className="mt-0.5 flex items-start gap-1.5 text-[12.5px] text-ink-2"><MapPin size={13} className="mt-0.5 shrink-0" /> Processed in {r.processed_in}</div>
              {!r.stays_in_uk && <div className="mt-1.5 text-[12.5px] font-semibold text-ink">{r.fix}</div>}
            </div>
          </div>
          <div className="mt-3 text-[11.5px] leading-relaxed text-ink-3">
            Set in <span className="font-mono">.env</span>: FDE_LLM_PROVIDER, FDE_BEDROCK_REGION, FDE_BEDROCK_MODEL_ID. Helen's rule (Day 1): customer data stays in the UK.
          </div>
        </Card>
        <Card className="overflow-hidden" testId="models">
          <div className="px-4 pt-3.5 text-[13px] font-semibold">Claude on Amazon Bedrock, called from London (eu-west-2)</div>
          <div className="px-4 text-[11.5px] text-ink-3">From each model's card in the Bedrock user guide, checked 5 Nov 2026. Prices in USD per million tokens.</div>
          <table className="mt-2 w-full text-left text-[12px]">
            <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
              <tr><th className="px-4 py-1.5">Model</th><th className="py-1.5">ID to call from London</th><th className="py-1.5 text-center">London in-Region</th><th className="py-1.5 pr-4 text-right">In / out</th></tr>
            </thead>
            <tbody>
              {s.models.map((m) => {
                const id = m.london_in_region === "yes" ? m.in_region_model_id : m.eu_profile_id;
                const current = id === r.model_id;
                return (
                  <tr key={m.model} data-testid={`model-${m.in_region_model_id}`} className={`border-t border-black/[0.05] ${current ? "bg-amber-50/60" : ""}`}>
                    <td className="px-4 py-2 font-semibold">{m.model}{current && <span className="ml-1.5 text-[10.5px] font-semibold text-amber">now</span>}</td>
                    <td className="py-2 font-mono text-[11px] text-ink-2">{id}</td>
                    <td className="py-2 text-center">{m.london_in_region === "yes" ? <CheckCircle2 size={15} className="inline text-teal" /> : <span className="text-[11px] font-semibold text-ember">EU Regions</span>}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{m.input_usd_per_m ? `${m.input_usd_per_m} / ${m.output_usd_per_m}` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="border-t border-black/[0.05] px-4 py-2.5 text-[11.5px] text-ink-2">A model ID that starts with <b>eu.</b> or <b>global.</b> is an inference profile: Bedrock may process the call in another Region.</div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card className="p-4" testId="selftest-card">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-[13.5px] font-semibold"><FlaskConical size={15} /> Offline check of the Bedrock client</div>
              <div className="text-[12px] text-ink-2">Runs ticket ENG-501's code on one document against a stand-in for Bedrock: no AWS call, no cost. Shows the exact Converse request.</div>
            </div>
            <div className="shrink-0"><Button onClick={run} disabled={busy === "test"} testId="selftest">{busy === "test" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run the check</Button></div>
          </div>
          {nb && <div className="mt-3"><NotBuilt ticket="ENG-501">{nb}. Open docs/tickets/ENG-501.md.</NotBuilt></div>}
          {test && (
            <div className="mt-3 space-y-2.5" data-testid="selftest-result">
              <Json value={test.request} />
              <div className="flex flex-wrap gap-1.5 text-[11.5px]">
                <Chip tone="teal">{test.fields.length} fields parsed</Chip>
                <Chip>{test.calls[0]?.input_tokens} input · {test.calls[0]?.output_tokens} output tokens</Chip>
                <Chip>{test.calls[0]?.latency_ms} ms</Chip>
              </div>
            </div>
          )}
        </Card>
        <Card className="p-4" testId="try-card">
          <div className="text-[13.5px] font-semibold">Read one document with the model in force now</div>
          <div className="text-[12px] text-ink-2">{s.settings.fake ? "The console is on the scripted model: this shows the scripted reply. Set FDE_LLM_PROVIDER=bedrock to call your account." : `Calls ${s.label}. Costs a fraction of a cent.`}</div>
          <div className="mt-3 flex items-center gap-2">
            <select data-testid="try-case-id" value={cid} onChange={(e) => setCid(e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1.5 font-mono text-[12px]">
              {CASES.map((c) => <option key={c}>{c}</option>)}
            </select>
            <Button variant="secondary" onClick={tryCase} disabled={busy === "try"} testId="try-case">{busy === "try" ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Read it</Button>
          </div>
          {err && <div className="mt-3 flex gap-2 rounded-lg bg-ember-50 px-3 py-2 text-[12px] text-ember"><CircleAlert size={14} className="mt-0.5 shrink-0" />{err}</div>}
          {tried && (
            <div className="mt-3" data-testid="try-result">
              {tried.blocked ? (
                <div className="rounded-lg bg-amber-50 px-3 py-2 text-[12px] text-amber">Guardrail blocked the {tried.blocked.where}: {tried.blocked.message}</div>
              ) : (
                <table className="w-full text-[12px]">
                  <tbody>
                    {tried.fields.map((f) => (
                      <tr key={f.name} className="border-t border-black/[0.05]">
                        <td className="py-1.5 text-ink-3">{f.label}</td>
                        <td className="py-1.5 font-semibold">{f.value || "—"}</td>
                        <td className="py-1.5 text-right"><span className={`rounded px-1.5 py-0.5 text-[10.5px] font-semibold ${STATUS_STYLE[f.status].chip}`}>{f.confidence.toFixed(2)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <div className="mt-2 flex flex-wrap gap-1.5 text-[11.5px]">
                {tried.calls.at(-1) && <Chip>{tried.calls.at(-1)!.input_tokens} in · {tried.calls.at(-1)!.output_tokens} out tokens</Chip>}
                {tried.cost_usd != null && <Chip tone="teal">USD {tried.cost_usd.toFixed(4)}</Chip>}
                <Chip tone={tried.residency.stays_in_uk ? "teal" : "ember"}>{tried.residency.stays_in_uk ? "Processed in London" : "Processed outside the UK"}</Chip>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
