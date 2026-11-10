// Small building blocks shared by every screen.
import type { ReactNode } from "react";

export function Card({ children, className = "", testId }: { children: ReactNode; className?: string; testId?: string }) {
  return (
    <div data-testid={testId} className={`rounded-xl border border-black/[0.06] bg-white shadow-[0_1px_2px_rgba(27,31,59,0.04)] ${className}`}>
      {children}
    </div>
  );
}

export function Kpi({ label, value, sub, tone = "ink" }: { label: string; value: ReactNode; sub?: string; tone?: "ink" | "teal" | "amber" | "ember" }) {
  const c = { ink: "text-ink", teal: "text-teal", amber: "text-amber", ember: "text-ember" }[tone];
  return (
    <Card className="px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">{label}</div>
      <div className={`mt-1 text-[22px] font-semibold leading-none tracking-tight ${c}`}>{value}</div>
      {sub && <div className="mt-1.5 text-[12px] text-ink-2">{sub}</div>}
    </Card>
  );
}

export function Button({ children, onClick, variant = "primary", disabled, testId }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost"; disabled?: boolean; testId?: string;
}) {
  const v = {
    primary: "bg-navy text-white hover:bg-navy-600",
    secondary: "border border-black/[0.1] bg-white text-ink hover:bg-mist",
    ghost: "text-ink-2 hover:bg-mist",
  }[variant];
  return (
    <button data-testid={testId} disabled={disabled} onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[12.5px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${v}`}>
      {children}
    </button>
  );
}

export function Chip({ children, tone = "mist" }: { children: ReactNode; tone?: "mist" | "teal" | "amber" | "ember" | "navy" }) {
  const t = {
    mist: "bg-mist text-ink-2", teal: "bg-teal-50 text-teal", amber: "bg-amber-50 text-amber",
    ember: "bg-ember-50 text-ember", navy: "bg-navy text-white",
  }[tone];
  return <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${t}`}>{children}</span>;
}

export function NotBuilt({ ticket, children }: { ticket: string; children: ReactNode }) {
  return (
    <div data-testid="not-built" className="rounded-xl border border-dashed border-amber bg-amber-50 p-5">
      <div className="text-[13px] font-semibold text-amber">Ticket {ticket} is not built yet</div>
      <div className="mt-1 text-[12.5px] leading-relaxed text-ink-2">{children}</div>
    </div>
  );
}
