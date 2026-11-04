// Small helpers for calling the FastAPI backend through Vite's /api proxy.

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch { /* not JSON */ }
    throw new ApiError(r.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return r.json() as Promise<T>;
}

export const api = {
  get: <T,>(url: string) => call<T>("GET", url),
  post: <T,>(url: string, body?: unknown) => call<T>("POST", url, body ?? {}),
  put: <T,>(url: string, body: unknown) => call<T>("PUT", url, body),
  del: <T,>(url: string) => call<T>("DELETE", url),
};

export type Area = "goals" | "process" | "data" | "risk" | "success";
export type Question = { id: string; area: Area; text: string; why: string; starred: boolean };
export type FindingKind = "pain_point" | "requirement" | "constraint" | "open_question";
export type Finding = {
  id: string; kind: FindingKind; title: string; detail: string; speaker: string; quote: string;
  frequency: number | null; impact: number | null; evidence_ok: boolean | null;
  review: "unreviewed" | "confirmed" | "wrong";
};
export type Criterion = {
  id: string; name: string; kind: "business" | "quality" | "guardrail"; metric: string;
  baseline: number | null; target: number | null; unit: string; direction: "increase" | "decrease";
  measured_how: string; owner: string; by_when: string; problems: string[];
};
export type UseCase = {
  id: string; name: string; description: string; value: number; feasibility: number; risk: number;
  excluded_reason: string; first_choice: boolean; score: number;
};

// ---- Day 2: solution design
export type Readiness = { name: string; status: "green" | "amber" | "red"; value: string; detail: string };
export type ColumnProfile = {
  column: string; rows: number; missing_pct: number; distinct: number; invalid_pct: number;
  bad_examples: string[]; pii_found: Record<string, number>; issues: string[];
};
export type ProfileResult = { rows: number; profiles: ColumnProfile[]; readiness: Readiness[] };
export type ArchNode = {
  id: string; label: string; kind: string; lane: "client" | "bank" | "aws" | "external"; row: number;
  region: string; hosting: string; customer_data: boolean; read_only: boolean;
};
export type Violation = { rule: string; message: string; node: string | null; edge: string[] | null };
export type Option = {
  id: string; name: string; summary: string; time_to_pilot_weeks: number; strengths: string[]; weaknesses: string[];
  cost: Record<string, unknown>; nodes: ArchNode[]; edges: { source: string; target: string; label: string }[];
  violations: Violation[] | null;
};
export type Rule = { rule: string; text: string; source: string };
export type CostRow = { id: string; name: string; parts: Record<string, number>; total_gbp: number; per_doc_gbp: number };
export type CostResult = {
  inputs: { docs: number; pages: number; minutes_saved: number }; options: CostRow[];
  curve: Record<string, number>[]; value_gbp: number; prices: Record<string, number>;
};
export type Adr = { file: string; markdown: string; checks: { check: string; ok: boolean }[] };
export type PlanTask = { id: string; name: string; phase: string; kind: string; owner: string; start_week: number; weeks: number; effort_days: number };
export type PlanPhase = { name: string; start_week: number; end_week: number; gate: { name: string; week: number; approver: string } };
export type PlanResult = {
  rules: { engagement_weeks: number; validation_weeks: number; production_gate_approver: string; stakeholders: string[] };
  plan: { team: { fdes: number; days_per_week: number }; phases: PlanPhase[]; tasks: PlanTask[] } | null;
  checks: { check: string; ok: boolean }[] | null;
};
