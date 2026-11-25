// Shared parts of the Model lab: the status, today's tickets, the model picker, and small formatting helpers.
import { Check } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Acc, type DistilStatus } from "../../api";
import { Chip } from "../../components/ui";

export function useDistil() {
  const [st, setSt] = useState<DistilStatus | null>(null);
  const reload = useCallback(() => api.get<DistilStatus>("/api/distil/status").then(setSt), []);
  useEffect(() => { reload(); }, [reload]);
  return { st, reload };
}

export const FIELD_NAMES: Record<string, string> = { full_name: "Full name", address: "Address", statement_date: "Statement date", issuer: "Issuer" };
export const KIND_NAMES: Record<string, string> = { utility_bill: "Utility bills", bank_statement: "Bank statements", council_tax: "Council tax bills" };
export const pct = (a: Acc | undefined | null) => (a && a.accuracy !== null ? `${a.accuracy.toFixed(1)}%` : "–");
export const gbp = (n: number) => `£${n.toLocaleString("en-GB")}`;

export function TicketChips11({ st }: { st: DistilStatus | null }) {
  if (!st) return null;
  const names = { "ENG-1101": "learn from what the teacher is sure of", "ENG-1102": "an honest confidence", "ENG-1103": "the weakest field decides" } as const;
  return (
    <div className="flex flex-wrap gap-1.5" data-testid="ml-tickets">
      {(Object.keys(names) as (keyof typeof names)[]).map((t) => (
        <span key={t} data-testid={`ticket-${t}`}><Chip tone={st.tickets[t] ? "teal" : "amber"}>{st.tickets[t] ? <Check size={11} /> : null}{t} {names[t]}{st.tickets[t] ? "" : ": not built"}</Chip></span>
      ))}
    </div>
  );
}

export function ModelPicker({ st, value, onChange }: { st: DistilStatus; value: string | null; onChange: (m: string) => void }) {
  if (!st.models.length) return <span className="text-[12.5px] text-ink-3">No model yet: train one on Teacher and student</span>;
  return (
    <select data-testid="model-picker" value={value ?? ""} onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-black/10 bg-white px-2 py-1.5 font-mono text-[12px]">
      {st.models.map((m) => <option key={m.name} value={m.name}>{m.name} · {m.read_files.join(" + ")}</option>)}
    </select>
  );
}

export function Bar({ value, max = 100, tone = "teal" }: { value: number; max?: number; tone?: "teal" | "ember" | "amber" | "navy" }) {
  const c = { teal: "bg-teal", ember: "bg-ember", amber: "bg-amber", navy: "bg-navy" }[tone];
  return <div className="h-1.5 w-full rounded-full bg-mist"><div className={`h-1.5 rounded-full ${c}`} style={{ width: `${Math.max(0, Math.min(100, (100 * value) / max))}%` }} /></div>;
}
