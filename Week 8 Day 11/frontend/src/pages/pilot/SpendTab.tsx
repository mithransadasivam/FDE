// Spend: what the pilot costs, and what stops it overspending. The model choice from the Platform tab has a price.
import { AlarmClock, Ban, CheckCircle2, Server, Trash2, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Spend } from "../../api";
import { Card, Chip, Kpi } from "../../components/ui";

export default function SpendTab() {
  const [d, setD] = useState<Spend | null>(null);
  useEffect(() => { api.get<Spend>("/api/pilot/spend").then(setD); }, []);
  if (!d) return null;
  const cur = d.models.find((m) => m.model_id === d.current);
  const max = Math.max(...d.models.map((m) => m.gbp_per_month ?? 0), 1);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3" data-testid="spend-kpis">
        <Kpi label="Monthly budget" value={d.budget ? `USD ${d.budget.limit_usd}` : "—"} sub={d.budget ? `alerts at ${d.budget.alerts.join(" and ")}` : "no plan yet: see Infrastructure"} tone="teal" />
        <Kpi label="Hard stop" value={d.budget?.action ? "On" : "Off"} sub={d.budget?.action ? "budget action denies Bedrock at 100%" : "an alert alone stops nothing"} tone={d.budget?.action ? "teal" : "ember"} />
        <Kpi label="Infrastructure" value={`USD ${d.infra.usd_per_day.toFixed(2)}`} sub={`a day: ${d.infra.endpoints} private endpoints, every hour they exist`} tone="amber" />
        <Kpi label="Model, per document" value={cur?.usd_per_doc != null ? `USD ${cur.usd_per_doc.toFixed(4)}` : "—"} sub={`${d.tokens_per_doc.input.toLocaleString()} in · ${d.tokens_per_doc.output.toLocaleString()} out tokens (${d.tokens_per_doc.measured ? "measured" : "Day 2 estimate"})`} />
      </div>
      <div className="grid grid-cols-[1.35fr_1fr] gap-4">
        <Card className="p-4" testId="model-cost">
          <div className="text-[13.5px] font-semibold">The price of keeping data in the UK</div>
          <div className="text-[12px] text-ink-2">Model cost a month at today's {d.docs_per_month.toLocaleString()} documents, in GBP. Only the models marked UK can be used.</div>
          <div className="mt-3 space-y-2.5">
            {d.models.map((m) => (
              <div key={m.model} data-testid={`cost-${m.model_id}`}>
                <div className="flex items-center justify-between text-[12.5px]">
                  <span className="font-semibold">{m.model} <span className="font-mono text-[11px] font-normal text-ink-3">{m.model_id}</span>{m.model_id === d.current && <span className="ml-1.5 text-[10.5px] font-semibold text-amber">now</span>}</span>
                  <span className="flex items-center gap-2">
                    {m.stays_in_uk ? <Chip tone="teal">UK</Chip> : <Chip tone="ember">leaves the UK</Chip>}
                    <span className="w-[64px] text-right font-semibold tabular-nums">{m.gbp_per_month != null ? `£${m.gbp_per_month}` : "—"}</span>
                  </span>
                </div>
                <div className="mt-1 h-2.5 rounded-full bg-mist">
                  {m.gbp_per_month != null && <div className={`h-2.5 rounded-full ${m.stays_in_uk ? "bg-teal" : "bg-ember/50"}`} style={{ width: `${Math.max(1.5, (100 * m.gbp_per_month) / max)}%` }} />}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-[11.5px] text-ink-3">Prices: Bedrock, USD per million tokens, from data/Day05_Slide10_bedrock_models.csv. — means no price in the file: check the Bedrock pricing page. {d.gbp_per_usd} GBP per USD.</div>
        </Card>
        <Card className="p-4" testId="controls">
          <div className="text-[13.5px] font-semibold">What stops the pilot overspending</div>
          <div className="mt-3 space-y-3 text-[12.5px]">
            <div className="flex gap-2.5"><Wallet size={16} className="mt-0.5 shrink-0 text-teal" /><div><b>A budget</b> emails at 80% of actual spend and when the forecast passes 100%.</div></div>
            <div className="flex gap-2.5"><Ban size={16} className="mt-0.5 shrink-0 text-teal" /><div><b>A budget action</b> attaches a deny policy to the pilot's role at 100%: every Bedrock call then fails.</div></div>
            <div className="flex gap-2.5"><AlarmClock size={16} className="mt-0.5 shrink-0 text-amber" /><div><b>Not real time.</b> Billing data reaches AWS Budgets a few times a day, so a runaway loop can overshoot before the stop.</div></div>
            <div className="flex gap-2.5"><Server size={16} className="mt-0.5 shrink-0 text-amber" /><div>{d.infra.note}</div></div>
            <div className="flex gap-2.5 rounded-lg bg-ember-50 p-2.5" data-testid="teardown"><Trash2 size={16} className="mt-0.5 shrink-0 text-ember" /><div><b>End of the day:</b> <span className="font-mono">terraform destroy</span> in infra/. Everything is code, so tomorrow's <span className="font-mono">terraform apply</span> brings it back in minutes.</div></div>
            {d.budget?.action && <div className="flex gap-2.5 text-[12px] text-ink-2"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-teal" />{d.budget.action}</div>}
          </div>
        </Card>
      </div>
    </div>
  );
}
