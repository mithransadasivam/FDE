import { CalendarRange, CheckCircle2, Diamond, Download, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type PlanResult } from "../../api";
import { Button, Card } from "../../components/ui";

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}
// a leading = + - @ would run as a formula in Excel, so a quote goes in front of it
const cell = (v: string | number) => {
  const t = String(v);
  return `"${(/^[=+\-@]/.test(t) ? `'${t}` : t).replace(/"/g, '""')}"`;
};

const KIND: Record<string, string> = {
  build: "#0E8F7E", data: "#5B6BBF", evaluation: "#30365E", security: "#9A9EB3", validation: "#E8552F", training: "#D98E04", handover: "#B7791F",
};
const PHASE_TINT = ["#EEF7F5", "#F4F5FA", "#FDEEE9"];

export default function PlanTab() {
  const [res, setRes] = useState<PlanResult | null>(null);
  useEffect(() => { api.get<PlanResult>("/api/design/plan").then(setRes); }, []);
  if (!res) return null;
  const { plan, rules, checks } = res;
  if (!plan) return (
    <Card className="p-8 text-center" testId="no-plan">
      <CalendarRange className="mx-auto text-ink-3" />
      <div className="mt-2 text-[14px] font-semibold">No delivery plan yet</div>
      <div className="mt-1 text-[12.5px] text-ink-2">Activity 4 writes engagement/delivery_plan.json in the format of data/Day02_Slide26_delivery_plan_format.md.</div>
      <div className="mt-1 text-[12px] text-ink-3">Client rules in force: {rules.engagement_weeks} weeks · validation {rules.validation_weeks} weeks · production gate by {rules.production_gate_approver}</div>
    </Card>
  );
  const W = rules.engagement_weeks;
  const LBL = 300, COL = (1080 - LBL) / W, RH = 30, TOP = 58;
  const tasks = [...plan.tasks].sort((a, b) => a.start_week - b.start_week || a.id.localeCompare(b.id));
  const H = TOP + tasks.length * RH + 20;
  const x = (week: number) => LBL + (week - 1) * COL;
  const used = plan.tasks.filter((t) => t.owner === "FDE").reduce((s, t) => s + t.effort_days, 0);
  const cap = plan.team.fdes * plan.team.days_per_week * W;
  const passed = checks?.filter((c) => c.ok).length ?? 0;
  const exportCsv = () => {
    const gate = Object.fromEntries(plan.phases.map((p) => [p.name, `${p.gate.name} (week ${p.gate.week}, ${p.gate.approver})`]));
    const head = ["Task", "Name", "Phase", "Kind", "Owner", "Start week", "Weeks", "Effort days", "Phase gate"];
    const rows = tasks.map((t) => [t.id, t.name, t.phase, t.kind, t.owner, t.start_week, t.weeks, t.effort_days, gate[t.phase] ?? ""]);
    // BOM so Excel reads the file as UTF-8
    download("delivery_plan.csv", "﻿" + [head, ...rows].map((r) => r.map(cell).join(",")).join("\r\n"), "text/csv;charset=utf-8");
  };
  const exportJson = () => download("delivery_plan.json", JSON.stringify(plan, null, 2), "application/json");
  return (
    <div className="grid grid-cols-[1fr_330px] gap-4">
      <Card className="p-4">
        <div className="flex items-center justify-between">
          <div className="text-[14px] font-semibold">Delivery plan · {W} weeks · {plan.team.fdes} FDEs</div>
          <div className="flex flex-wrap gap-2.5 text-[10.5px] text-ink-3">{Object.entries(KIND).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{k}</span>)}</div>
        </div>
        <svg data-testid="gantt" viewBox={`0 0 1080 ${H}`} className="mt-2 w-full">
          {plan.phases.map((p, i) => (
            <g key={p.name}>
              <rect x={x(p.start_week)} y={4} width={(p.end_week - p.start_week + 1) * COL} height={H - 8} fill={PHASE_TINT[i % 3]} rx="6" />
              <text x={x(p.start_week) + 8} y={20} fontSize="11.5" fontWeight="700" fill="#1B1F3B">{p.name}</text>
            </g>
          ))}
          {Array.from({ length: W }, (_, i) => (
            <g key={i}><line x1={x(i + 1)} x2={x(i + 1)} y1={28} y2={H - 6} stroke="#E2E4EC" />
              <text x={x(i + 1) + COL / 2} y={44} textAnchor="middle" fontSize="10.5" fill="#9A9EB3">Week {i + 1}</text></g>
          ))}
          {tasks.map((t, i) => {
            const y = TOP + i * RH;
            return (
              <g key={t.id} data-testid={`task-${t.id}`}>
                <text x={8} y={y + 18} fontSize="11.5" fill="#1B1F3B"><tspan fontWeight="700">{t.id}</tspan> {t.name.length > 34 ? t.name.slice(0, 33) + "…" : t.name}</text>
                <rect x={x(t.start_week) + 3} y={y + 5} width={Math.max(t.weeks * COL - 6, 8)} height={RH - 10} rx="5" fill={KIND[t.kind] ?? "#9A9EB3"} opacity={t.owner === "FDE" ? 1 : 0.55} />
                <text x={x(t.start_week) + 10} y={y + 19} fontSize="10" fontWeight="600" fill="#FFFFFF">{t.owner}{t.owner === "FDE" ? ` · ${t.effort_days}d` : ""}</text>
              </g>
            );
          })}
          {plan.phases.map((p) => (
            <g key={p.name + "g"}>
              <rect x={x(p.gate.week) + COL - 22} y={30} width={13} height={13} transform={`rotate(45 ${x(p.gate.week) + COL - 15.5} 36.5)`} fill="#E8552F" />
            </g>
          ))}
        </svg>
        <div className="mt-2 grid grid-cols-3 gap-2">
          {plan.phases.map((p) => (
            <div key={p.name} className="flex items-start gap-2 rounded-lg bg-mist px-3 py-2 text-[11.5px]">
              <Diamond size={13} className="mt-0.5 shrink-0 fill-ember text-ember" />
              <div><b>{p.gate.name}</b><div className="text-ink-3">Week {p.gate.week} · {p.gate.approver}</div></div>
            </div>
          ))}
        </div>
      </Card>
      <div className="space-y-3">
        <Card className="p-4" testId="plan-checks">
          <div className="text-[14px] font-semibold">Plan checks</div>
          <div data-testid="plan-score" className={`text-[12px] ${passed === checks?.length ? "text-teal" : "text-ember"}`}>{passed} of {checks?.length} passed</div>
          <div className="mt-2 space-y-1.5">
            {checks?.map((c) => (
              <div key={c.check} className="flex items-start gap-2 text-[12.5px]">
                {c.ok ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-teal" /> : <XCircle size={15} className="mt-0.5 shrink-0 text-ember" />}{c.check}
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-[13px] font-semibold">FDE capacity</div>
          <div className="mt-2 h-3 overflow-hidden rounded-full bg-mist"><div className={`h-full ${used <= cap ? "bg-teal" : "bg-ember"}`} style={{ width: `${Math.min(100, (used / cap) * 100)}%` }} /></div>
          <div className="mt-1 text-[12px] text-ink-2">{used} of {cap} person-days planned</div>
          <div className="mt-3 flex gap-2">
            <Button variant="secondary" onClick={exportCsv} testId="export-csv"><Download size={14} />Export CSV</Button>
            <Button variant="secondary" onClick={exportJson} testId="export-json"><Download size={14} />Export JSON</Button>
          </div>
          <div className="mt-3 text-[11.5px] text-ink-3">Client rules from engagement/client_rules.json: validation {rules.validation_weeks} weeks; production gate by {rules.production_gate_approver}.</div>
        </Card>
      </div>
    </div>
  );
}
