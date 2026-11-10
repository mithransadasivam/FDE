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

// ---------------------------------------------------------------- Day 3: the UC1 prototype (contract: backend/app/prototype/models.py)
export type FieldStatus = "ok" | "check" | "doubtful" | "not_on_page" | "missing" | "confirmed";
export type CaseField = {
  name: "full_name" | "address" | "statement_date" | "issuer"; label: string; value: string; confidence: number;
  status: FieldStatus; box: [number, number, number, number] | null; page_text: string; note: string;
};
export type PolicyCheck = { id: "name" | "address" | "date" | "issuer"; label: string; status: "pass" | "fail" | "look"; detail: string };
export type Application = {
  case_id: string; applicant_name: string; address_line1: string; town: string; postcode: string;
  application_date: string; received_date: string; channel: string; document: string;
};
export type DecisionEntry = { at: string; case_id: string; decision: "approve" | "ask_applicant" | "escalate"; analyst_id: string; reason: string };
export type CaseDetail = {
  application: Application; document: { image: string; file: string };
  fields: CaseField[] | null; checks: PolicyCheck[] | null; recommendation: "ready" | "fails" | "look" | null;
  decision: DecisionEntry | null; not_built: string[];
};
export type QueueRow = {
  case_id: string; applicant_name: string; postcode: string; received_date: string; channel: string;
  state: "new" | "ready" | "fails" | "look" | "not_built"; issuer: string; doubtful: number; decision: string | null;
};
export type DemoCriterion = { id: string; name: string; target: number; unit: string; measure: string; value: number | null; status: "on_track" | "off_track" | "pending" | "pilot"; note: string };
export type DemoResult = {
  documents: number; fields: number; correct: number; accuracy: number; caught: number;
  wrong: { case_id: string; field: string; label: string; got: string; expected: string; status: FieldStatus; confidence: number; flagged: boolean }[];
  rules: { agree: number; compared: number; sent_to_person: number; date_counted_from: string;
    disagreements: { case_id: string; prototype: string; tom: string; tom_note: string; check: string; detail: string }[] };
  criteria: DemoCriterion[];
};
export type PrReview = {
  verdict: "looks_good" | "comments" | "changes_needed"; summary: string; reviewed_at: string; base: string; cost_usd: number | null;
  findings: { file: string; line?: number; severity: "high" | "medium" | "low"; rule: string; message: string }[];
  stats: { files: string[]; lines_added: number; lines_removed: number };
};

// ---------------------------------------------------------------- Day 4: evaluation (backend/app/evaluation)
export type Score = { correct: number; total: number; accuracy: number };
export type FieldError = { case_id: string; field: string; got: string; expected: string };
export type EvalRun = {
  name: string; prompt: string; set: "real" | "synthetic" | "all"; at: string; cases: number;
  score: { overall: Score; per_field: Record<string, Score>; per_slice: Record<string, Score>; errors: FieldError[] };
  rules: { agree: number; compared: number; errors: FieldError[] };
};
export type RunSummary = { name: string; prompt: string; set: string; at: string; cases: number; overall: Score; rules: { agree: number; compared: number } };
export type TaxonomyRow = { type: string; count: number; share: number; cumulative: number };
export type Agreement = {
  n: number; agree: number; percent: number; kappa: number; tp: number; fp: number; fn: number; tn: number;
  caught: number | null; cleared: number | null; disagreements: string[];
};
export type LabelItem = { item: string; case_id: string; field: string; value: string; label: "correct" | "wrong" | null; box: [number, number, number, number] | null; image: string };
export type LabelRound = { round: number; guideline: string; at: string; agreement: Agreement };
export type JudgeInfo = { judge: string; field: string; failure_type: string; prompts: string[] };
export type JudgeResult = {
  judge: string; prompt: string; field: string; failure_type: string; at: string; agreement: Agreement;
  verdicts: Record<string, { verdict: "pass" | "fail"; reason: string; value: string; expert: "pass" | "fail"; expected: string }>;
};

// ---------------------------------------------------------------- Day 5: the pilot on the client's cloud (backend/app/platform)
export type Residency = { model_id: string; region: string; routing: "in-region" | "geo" | "global"; processed_in: string; stays_in_uk: boolean; model: string; fix: string };
export type BedrockModel = { model: string; in_region_model_id: string; london_in_region: string; eu_profile_id: string; input_usd_per_m: string; output_usd_per_m: string; price_basis: string; source: string };
export type PilotStatus = {
  settings: { fake: boolean; provider: string; region: string; model_id: string; guardrail_id: string; guardrail_version: string; guardrail_policy: string };
  label: string; residency: Residency; models: BedrockModel[];
};
export type Call = { input_tokens: number; output_tokens: number; latency_ms?: number; stop_reason?: string };
export type SelfTest = { case_id: string; request: Record<string, unknown>; fields: { name: string; value: string; word_ids: string[] }[]; calls: Call[]; residency: Residency };
export type TryResult = { case_id: string; label: string; residency: Residency; blocked: { where: string; message: string } | null; fields: CaseField[]; calls: Call[]; cost_usd?: number | null };
export type PilotCheck = { rule: string; label: string; owner: string; ok: boolean; evidence: string; resources: string[] };
export type PilotPlan = { file: string; terraform_version: string; variables: Record<string, unknown>; resources: { address: string; type: string; name: string }[]; checks: PilotCheck[] };
export type ProbeResult = {
  case_id: string; title: string; tests: string; kind: "injection" | "leak" | "control"; blocked: { where: string; message: string } | null;
  fields: Record<string, { value: string; status: string; right: boolean }>; verdict: "good" | "bad"; outcome: string;
};
export type ProbeRun = { policy: string; at: string; label: string; results: ProbeResult[]; stopped: number; attacks: number };
export type RunWithUsage = RunSummary & { guardrail?: string; model?: string; usage?: { documents: number; input_tokens: number; output_tokens: number }; blocked?: { case_id: string }[]; per_field?: Record<string, Score> };
export type GuardrailPolicy = {
  name: string; description: string; content_filters: string[]; prompt_attack: boolean; denied_topics: string[]; masked: string[]; blocked: string[];
  probes: ProbeRun | null; runs: RunWithUsage[];
};
export type Spend = {
  budget: { limit_usd: number; alerts: string[]; action: string | null } | null;
  tokens_per_doc: { input: number; output: number; measured: boolean };
  models: { model: string; model_id: string; stays_in_uk: boolean; usd_per_doc: number | null; gbp_per_month: number | null }[];
  docs_per_month: number; gbp_per_usd: number; infra: { endpoints: number; usd_per_day: number; note: string }; current: string;
};
