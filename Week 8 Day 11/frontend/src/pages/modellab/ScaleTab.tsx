// Client scale (Activity 4): the month at the bank's volumes, today and during the remediation, the pilot alone (ADR-003)
// against the cascade. The October numbers are measured; the volumes and internal rates are Martin's (Day11_Slide26_volumes.json).
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type ScaleResult } from "../../api";
import { Card, Kpi } from "../../components/ui";
import { ModelPicker, gbp, useDistil } from "./parts";

export default function ScaleTab() {
  const { st } = useDistil();
  const [model, setModel] = useState<string | null>(null);
  const [s, setS] = useState<ScaleResult | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (st && !model) setModel(st.active); }, [st]);
  useEffect(() => {
    if (!model || !st) return;
    setBusy(true);
    api.get<ScaleResult>(`/api/distil/scale?model=${model}&threshold=${st.threshold}`).then(setS).finally(() => setBusy(false));
  }, [model]);
  if (!st) return null;
  const v = st.volumes;
  const rows: [string, (m: ScaleResult["months"]["today"]["pilot"]) => string][] = [
    ["Sonnet calls", (m) => m.sonnet_calls.toLocaleString()],
    ["Model calls (Bedrock, London)", (m) => gbp(m.model_gbp)],
    ["Running the small model", (m) => (m.fixed_gbp ? gbp(m.fixed_gbp) : "–")],
    ["Fields an analyst checks", (m) => m.fields_to_person.toLocaleString()],
    ["Analyst time", (m) => `${m.people_hours} h · ${gbp(m.people_gbp)}`],
  ];
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><span className="text-[13px] text-ink-2">At the threshold chosen on Cascade: <b className="font-mono">{st.threshold.toFixed(2)}</b></span>
        {busy && <Loader2 size={14} className="animate-spin text-ink-3" />}
        <span className="ml-auto text-[12px] text-ink-3">Model</span><ModelPicker st={st} value={model} onChange={setModel} /></div>
      {s && s.model && (
        <>
          <div className="grid grid-cols-4 gap-3" data-testid="scale-kpis">
            <Kpi label="Errors that slip through, October" value={`${s.october.cascade.slipped} vs ${s.october.pilot.slipped}`} sub="the cascade vs the pilot alone" tone="teal" />
            <Kpi label="Answered at the counter" value={`${Math.round(100 * s.counter.answered_at_counter)}%`} sub={`in ${s.counter.cascade_ms_p50} ms; the pilot takes ${(s.counter.pilot_ms_p50 / 1000).toFixed(1)} s (target ${s.counter.target_ms / 1000} s)`} tone="teal" />
            <Kpi label="A month in the remediation" value={<span data-testid="remediation-total">{gbp(s.months.remediation.cascade.total_gbp)}</span>} sub={`the pilot alone: ${gbp(s.months.remediation.pilot.total_gbp)}`} tone="teal" />
            <Kpi label="It pays from" value={<span data-testid="breakeven">{s.breakeven_docs_per_month ? s.breakeven_docs_per_month.toLocaleString() : "never"}</span>} sub="documents a month" />
          </div>
          <Card className="overflow-hidden" testId="scale-table">
            <table className="w-full text-[12.5px]">
              <thead className="bg-mist text-left text-[10.5px] uppercase tracking-wide text-ink-3">
                <tr><th className="px-4 py-2">A month</th><th colSpan={2} className="border-l border-black/[0.06] px-3">Today · {v.business_as_usual_docs_per_month.toLocaleString()} documents</th>
                  <th colSpan={2} className="border-l border-black/[0.06] px-3">Remediation · {(v.business_as_usual_docs_per_month + v.remediation_docs_per_month).toLocaleString()} documents</th></tr>
                <tr><th className="px-4 py-1" /><th className="border-l border-black/[0.06] px-3">Pilot alone</th><th className="px-3">Cascade</th><th className="border-l border-black/[0.06] px-3">Pilot alone</th><th className="px-3">Cascade</th></tr>
              </thead>
              <tbody>
                {rows.map(([label, f]) => (
                  <tr key={label} className="border-t border-black/[0.05]"><td className="px-4 py-1.5">{label}</td>
                    <td className="border-l border-black/[0.06] px-3">{f(s.months.today.pilot)}</td><td className="px-3">{f(s.months.today.cascade)}</td>
                    <td className="border-l border-black/[0.06] px-3">{f(s.months.remediation.pilot)}</td><td className="px-3">{f(s.months.remediation.cascade)}</td></tr>
                ))}
                <tr className="border-t-2 border-black/10 font-semibold"><td className="px-4 py-2">In all</td>
                  <td className="border-l border-black/[0.06] px-3">{gbp(s.months.today.pilot.total_gbp)}</td><td className="px-3">{gbp(s.months.today.cascade.total_gbp)}</td>
                  <td className="border-l border-black/[0.06] px-3">{gbp(s.months.remediation.pilot.total_gbp)}</td><td className="px-3 text-teal">{gbp(s.months.remediation.cascade.total_gbp)}</td></tr>
              </tbody>
            </table>
          </Card>
          <Card className="p-4 text-[12px] text-ink-2" testId="scale-assumptions">
            <div className="text-[12.5px] font-semibold text-ink">Measured, and assumed</div>
            <div className="mt-1"><b>Measured on October:</b> errors, fields to a person, Sonnet calls and tokens a document (cascade {s.october.cascade.sonnet_calls} calls for 200 documents, pilot {s.october.pilot.sonnet_calls}), and the time to an answer.</div>
            <div className="mt-1"><b>Assumed, agreed with Martin (data/Day11_Slide26_volumes.json):</b> {v.small_model_host} at {gbp(v.small_model_host_gbp_per_month)} a month; {v.upkeep_hours_per_month} engineer hours a month at {gbp(v.engineer_gbp_per_hour)} ({v.upkeep.toLowerCase()}); an analyst checks a field in {v.analyst_seconds_per_field_check} s at {gbp(v.analyst_gbp_per_hour)} an hour.</div>
            <div className="mt-1">Write it up as ADR-008 on <b>Design & cost → Decision record</b>.</div>
          </Card>
        </>
      )}
    </div>
  );
}
