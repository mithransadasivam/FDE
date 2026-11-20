// Infrastructure: the pilot's Terraform plan, drawn as the network it will create, and checked against the bank's rules (ENG-502).
import { CheckCircle2, ChevronDown, ChevronRight, Globe, KeyRound, Lock, ScrollText, Server, ShieldCheck, Wallet, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type PilotCheck, type PilotPlan } from "../../api";
import { Card, Chip, NotBuilt } from "../../components/ui";

type Box = { id: string; title: string; sub: string; icon: any; rules: string[] };

function Node({ b, checks }: { b: Box; checks: Record<string, PilotCheck> }) {
  const bad = b.rules.some((r) => checks[r] && !checks[r].ok);
  const known = b.rules.some((r) => checks[r]);
  return (
    <div data-testid={`node-${b.id}`} data-bad={bad}
      className={`rounded-lg border-2 bg-white px-2.5 py-2 ${bad ? "border-ember shadow-[0_0_0_3px_rgba(232,85,47,0.12)]" : known ? "border-teal/60" : "border-black/10"}`}>
      <div className="flex items-center gap-1.5 text-[12px] font-semibold"><b.icon size={13} className={bad ? "text-ember" : "text-navy"} />{b.title}</div>
      <div className="mt-0.5 font-mono text-[10.5px] leading-snug text-ink-2">{b.sub}</div>
    </div>
  );
}

const Arrow = ({ label }: { label?: string }) => (
  <div className="flex flex-col items-center justify-center px-1 text-ink-3">
    {label && <span className="mb-0.5 whitespace-nowrap text-[9.5px]">{label}</span>}
    <span className="text-[15px] leading-none">→</span>
  </div>
);

export default function InfraTab() {
  const [p, setP] = useState<PilotPlan | null>(null);
  const [missing, setMissing] = useState("");
  const [nb, setNb] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    api.get<PilotPlan>("/api/pilot/plan").then(setP).catch((e) => {
      if (e instanceof ApiError && e.status === 404) setMissing(e.message);
      else if (e instanceof ApiError && e.status === 501) setNb(e.message);
      else throw e;
    });
  }, []);
  if (missing) return (
    <Card className="p-5" testId="no-plan">
      <div className="text-[14px] font-semibold">No Terraform plan yet</div>
      <div className="mt-1 text-[13px] text-ink-2">Terraform describes the pilot as code in <span className="font-mono">infra/</span>. Make a plan, save it as JSON, and this tab checks it against the bank's rules before anything is created:</div>
      <pre className="mt-2 rounded-lg bg-navy px-3 py-2 text-[12.5px] leading-relaxed text-white">cd infra{"\n"}terraform init{"\n"}terraform plan -out pilot.tfplan{"\n"}terraform show -json pilot.tfplan {">"} pilot.plan.json</pre>
    </Card>
  );
  if (nb) return <NotBuilt ticket="ENG-502">{nb}. Open docs/tickets/ENG-502.md.</NotBuilt>;
  if (!p) return null;
  const checks = Object.fromEntries(p.checks.map((c) => [c.rule, c]));
  const v = p.variables as Record<string, string>;
  const passed = p.checks.filter((c) => c.ok).length;
  const has = (t: string) => p.resources.some((r) => r.type === t);
  const box = (id: string, title: string, sub: string, icon: any, rules: string[]): Box => ({ id, title, sub, icon, rules });
  return (
    <div className="space-y-4">
      <Card className="p-4" testId="diagram">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[13.5px] font-semibold">What terraform apply will create</div>
            <div className="text-[12px] text-ink-2">Drawn from <span className="font-mono">{p.file}</span> · {p.resources.length} resources · Terraform {p.terraform_version}. A red box breaks a rule.</div>
          </div>
          <Chip tone={passed === p.checks.length ? "teal" : "ember"}>{passed} of {p.checks.length} rules met</Chip>
        </div>
        <div className="mt-4 grid grid-cols-[150px_1fr_210px] gap-3">
          <div className="rounded-xl bg-mist p-2.5">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-3">The analyst</div>
            <Node b={box("browser", "Browser", "password: analyst", Globe, [])} checks={checks} />
            <div className="my-1.5 text-center text-ink-3">↓ HTTPS</div>
            <Node b={box("url", "Function URL", "sign-in required", Lock, [])} checks={checks} />
          </div>
          <div className={`rounded-xl border-2 border-dashed p-2.5 ${checks.no_internet?.ok === false ? "border-ember" : "border-navy/25"}`}>
            <div className="mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-ink-3">
              <span>VPC 10.50.0.0/16 · private subnet · {v.region}</span>
              <span className={checks.no_internet?.ok === false ? "text-ember" : "text-teal"}>{has("aws_nat_gateway") || has("aws_internet_gateway") ? "route to the internet" : "no route to the internet"}</span>
            </div>
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-1">
              <Node b={box("lambda", "Lambda · uc1-pilot", `python3.12 · calls ${v.model_id}`, Server, ["residency", "model_in_region", "secrets"])} checks={checks} />
              <Arrow label="private DNS" />
              <div className="space-y-2">
                <Node b={box("ep-bedrock", "Endpoint · bedrock-runtime", "Interface · own policy", ShieldCheck, ["private_model"])} checks={checks} />
                <Node b={box("ep-secrets", "Endpoint · secretsmanager", "Interface", KeyRound, [])} checks={checks} />
              </div>
            </div>
            <div className="mt-2.5 grid grid-cols-2 gap-2">
              <Node b={box("role", "IAM role", "one model · this account's guardrails", KeyRound, ["least_privilege"])} checks={checks} />
              <Node b={box("logs", "Logs", "/aws/lambda/uc1-pilot · 30 days", ScrollText, [])} checks={checks} />
            </div>
            <div data-testid="network-facts" className="mt-2.5 grid grid-cols-3 gap-2 text-[11px] text-ink-2">
              {[["Internet gateway", has("aws_internet_gateway") ? "present" : "none"], ["NAT gateway", has("aws_nat_gateway") ? "present" : "none"],
                ["Security groups", "HTTPS to the endpoints only"]].map(([k, val]) => (
                <div key={k} className="rounded-lg bg-mist px-2.5 py-1.5"><div className="text-[10px] font-semibold uppercase tracking-wide text-ink-3">{k}</div>
                  <div className={`font-semibold ${val === "present" ? "text-ember" : "text-ink"}`}>{val}</div></div>
              ))}
            </div>
          </div>
          <div className="space-y-2 rounded-xl bg-mist p-2.5">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-3">AWS services, London</div>
            <Node b={box("bedrock", "Amazon Bedrock", `${v.model_id} · guardrail ${v.guardrail_policy}`, Server, ["model_in_region"])} checks={checks} />
            <Node b={box("secrets", "Secrets Manager", "analyst password", Lock, ["secrets"])} checks={checks} />
            <Node b={box("audit", "Invocation logging", "every call → CloudWatch, 30 days", ScrollText, ["audit"])} checks={checks} />
            <Node b={box("budget", "Budget", `USD ${v.budget_usd} a month · stop action`, Wallet, ["spend"])} checks={checks} />
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden" testId="rules">
        <div className="flex items-center justify-between px-4 py-3">
          <div>
            <div className="text-[13.5px] font-semibold">The bank's rules, checked on the plan</div>
            <div className="text-[12px] text-ink-2">The same rules as Day 2's architecture checks, now on the real infrastructure. Fix a failing rule in <span className="font-mono">infra/</span>, plan again, check again.</div>
          </div>
        </div>
        {p.checks.map((c) => (
          <div key={c.rule} data-testid={`rule-${c.rule}`} data-ok={c.ok} className={`flex items-start gap-3 border-t border-black/[0.05] px-4 py-2.5 ${c.ok ? "" : "bg-ember-50/60"}`}>
            {c.ok ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-teal" /> : <XCircle size={16} className="mt-0.5 shrink-0 text-ember" />}
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-semibold">{c.label} <span className="font-normal text-ink-3">· {c.owner}</span></div>
              <div className={`text-[12px] ${c.ok ? "text-ink-2" : "font-semibold text-ember"}`}>{c.evidence}</div>
            </div>
            <span className="shrink-0 font-mono text-[10.5px] text-ink-3">{c.rule}</span>
          </div>
        ))}
      </Card>

      <Card className="px-4 py-3">
        <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 text-[12.5px] font-semibold" data-testid="toggle-resources">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />} All {p.resources.length} resources in the plan
        </button>
        {open && (
          <div className="mt-2 grid grid-cols-3 gap-x-4 gap-y-0.5 font-mono text-[11px] text-ink-2" data-testid="resources">
            {p.resources.map((r) => <div key={r.address} className="truncate">{r.address}</div>)}
          </div>
        )}
      </Card>
    </div>
  );
}
