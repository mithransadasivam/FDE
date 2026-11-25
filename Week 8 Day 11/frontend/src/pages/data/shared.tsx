// Pieces shared by Ask the data and the Data agent tabs (Day 7).
import { ShieldCheck, UserRound } from "lucide-react";
import type { DataUser } from "../../api";

type Cell = string | number | boolean | null;

export function fmt(v: Cell): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v)) return v.slice(0, 16).replace("T", " ");
  return v;
}

/** A short text for a result: one value, or the first rows. */
export function brief(rows: Cell[][] | null | undefined, max = 3): string {
  if (!rows) return "—";
  if (rows.length === 0) return "no rows";
  if (rows.length === 1 && rows[0].length === 1) return fmt(rows[0][0]);
  const s = rows.slice(0, max).map((r) => r.map(fmt).join(" · ")).join("; ");
  return rows.length > max ? `${s}; … (${rows.length} rows)` : s;
}

export function ResultTable({ columns, rows, testId, max = 50 }: { columns: string[]; rows: Cell[][]; testId?: string; max?: number }) {
  return (
    <div className="overflow-auto rounded-lg border border-black/[0.06]" data-testid={testId}>
      <table className="w-full text-left text-[12.5px]">
        <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
          <tr>{columns.map((c) => <th key={c} className="px-3 py-1.5 font-semibold">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, max).map((r, i) => (
            <tr key={i} className="border-t border-black/[0.05]">
              {r.map((v, j) => <td key={j} className={`px-3 py-1.5 ${typeof v === "number" ? "tabular-nums" : ""} ${v === "[hidden]" ? "italic text-ink-3" : ""}`}>{fmt(v)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > max && <div className="border-t border-black/[0.05] px-3 py-1.5 text-[11.5px] text-ink-3">{rows.length - max} more rows</div>}
    </div>
  );
}

export function Sql({ sql, testId, tone = "plain" }: { sql: string; testId?: string; tone?: "plain" | "secured" | "refused" }) {
  const t = { plain: "bg-navy text-white/90", secured: "bg-teal-50 text-ink border border-teal/30", refused: "bg-ember-50 text-ink border border-ember/30" }[tone];
  return <pre data-testid={testId} className={`overflow-auto whitespace-pre-wrap rounded-lg px-3 py-2 font-mono text-[11.5px] leading-relaxed ${t}`}>{sql}</pre>;
}

export function UserCard({ u, active, onClick }: { u: DataUser; active?: boolean; onClick?: () => void }) {
  return (
    <button data-testid={`user-${u.id}`} onClick={onClick}
      className={`flex w-full items-start gap-2.5 rounded-xl border px-3 py-2.5 text-left transition ${active ? "border-navy bg-navy text-white" : "border-black/[0.06] bg-white hover:border-black/20"}`}>
      <span className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full ${active ? "bg-ember" : "bg-mist"}`}><UserRound size={14} /></span>
      <span className="min-w-0">
        <span className="block text-[13px] font-semibold">{u.name}</span>
        <span className={`block text-[11.5px] ${active ? "text-white/70" : "text-ink-2"}`}>{u.title}</span>
        <span className={`mt-1 flex items-center gap-1 text-[11px] ${active ? "text-[#5FD3C1]" : "text-teal"}`}><ShieldCheck size={11} /> {u.scope}</span>
      </span>
    </button>
  );
}
