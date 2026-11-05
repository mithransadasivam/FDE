// Ticket ENG-102, part B: the use-case matrix. Value (y) against feasibility (x), coloured by risk.
import type { UseCase } from "../api";

const W = 560;
const H = 360;
const PLOT = { left: 48, right: 540, top: 16, bottom: 310 };
const LOW = 0.5; // axis runs 1-5; the padding keeps bubbles on the edge inside the plot
const HIGH = 5.5;

const x = (feasibility: number) => PLOT.left + ((feasibility - LOW) / (HIGH - LOW)) * (PLOT.right - PLOT.left);
const y = (value: number) => PLOT.bottom - ((value - LOW) / (HIGH - LOW)) * (PLOT.bottom - PLOT.top);

const riskColour = (risk: number) => (risk <= 2 ? "#0E8F7E" : risk === 3 ? "#D98E04" : "#E8552F");
const shortName = (name: string) => (name.length > 22 ? name.slice(0, 21) + "…" : name);

export default function UseCaseMatrix({ useCases, onPick }: { useCases: UseCase[]; onPick?: (u: UseCase) => void }) {
  const midX = x(3);
  const midY = y(3);
  return (
    <svg data-testid="usecase-matrix" viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label="Use cases: value against feasibility">
      {/* quadrants, split at 3 on both axes */}
      <rect x={midX} y={PLOT.top} width={PLOT.right - midX} height={midY - PLOT.top} className="fill-teal-50" />
      <rect x={PLOT.left} y={PLOT.top} width={midX - PLOT.left} height={midY - PLOT.top} className="fill-mist" />
      <rect x={midX} y={midY} width={PLOT.right - midX} height={PLOT.bottom - midY} className="fill-mist" />
      <rect x={PLOT.left} y={midY} width={midX - PLOT.left} height={PLOT.bottom - midY} className="fill-white" />
      <rect x={PLOT.left} y={PLOT.top} width={PLOT.right - PLOT.left} height={PLOT.bottom - PLOT.top} fill="none" stroke="#D9DBE6" />
      <line x1={midX} y1={PLOT.top} x2={midX} y2={PLOT.bottom} stroke="#D9DBE6" strokeDasharray="4 3" />
      <line x1={PLOT.left} y1={midY} x2={PLOT.right} y2={midY} stroke="#D9DBE6" strokeDasharray="4 3" />

      <g className="fill-ink-3 text-[11px] font-semibold uppercase tracking-wide">
        <text x={PLOT.right - 6} y={PLOT.top + 14} textAnchor="end" className="fill-teal">Quick wins</text>
        <text x={PLOT.left + 6} y={PLOT.top + 14}>Big bets</text>
        <text x={PLOT.right - 6} y={PLOT.bottom - 8} textAnchor="end">Fill-ins</text>
        <text x={PLOT.left + 6} y={PLOT.bottom - 8}>Not now</text>
      </g>

      {/* axes */}
      {[1, 2, 3, 4, 5].map((n) => (
        <g key={n} className="fill-ink-2 text-[11px]">
          <text x={x(n)} y={PLOT.bottom + 15} textAnchor="middle">{n}</text>
          <text x={PLOT.left - 10} y={y(n) + 4} textAnchor="end">{n}</text>
        </g>
      ))}
      <text x={(PLOT.left + PLOT.right) / 2} y={H - 22} textAnchor="middle" className="fill-ink-2 text-[12px] font-medium">
        Feasibility: how easily we can build it →
      </text>
      <text transform={`translate(12 ${(PLOT.top + PLOT.bottom) / 2}) rotate(-90)`} textAnchor="middle" className="fill-ink-2 text-[12px] font-medium">
        Value to the client →
      </text>

      {/* one bubble per use case */}
      {useCases.map((u) => {
        const excluded = u.excluded_reason.trim() !== "";
        const cx = x(u.feasibility);
        const cy = y(u.value);
        const colour = riskColour(u.risk);
        return (
          <g
            key={u.id}
            data-testid={`uc-${u.id}`}
            data-first={u.first_choice ? "true" : "false"}
            data-excluded={excluded ? "true" : "false"}
            onClick={excluded ? undefined : () => onPick?.(u)}
            style={{ cursor: excluded || !onPick ? "default" : "pointer" }}
          >
            <title>{excluded ? `${u.name}: out of scope (${u.excluded_reason})` : `${u.name}: value ${u.value}, feasibility ${u.feasibility}, risk ${u.risk}`}</title>
            {u.first_choice && !excluded && <circle cx={cx} cy={cy} r={22} fill="none" stroke="#E8552F" strokeWidth={3} />}
            {excluded ? (
              <>
                <circle cx={cx} cy={cy} r={16} fill="#F4F5FA" stroke="#9A9EB3" strokeWidth={1.5} strokeDasharray="4 3" />
                <line x1={cx - 11} y1={cy - 11} x2={cx + 11} y2={cy + 11} stroke="#9A9EB3" strokeWidth={1.5} />
                <line x1={cx - 11} y1={cy + 11} x2={cx + 11} y2={cy - 11} stroke="#9A9EB3" strokeWidth={1.5} />
              </>
            ) : (
              <circle cx={cx} cy={cy} r={16} fill={colour} fillOpacity={0.92} />
            )}
            <text x={cx} y={cy + 4} textAnchor="middle" className={excluded ? "fill-ink-3 text-[11px] font-bold" : "fill-white text-[11px] font-bold"}>{u.id}</text>
            <text x={cx} y={cy + 32} textAnchor="middle" className={excluded ? "fill-ink-3 text-[10.5px]" : "fill-ink text-[10.5px] font-medium"}>
              {u.first_choice && !excluded ? "★ " : ""}{shortName(u.name)}
            </text>
            {excluded && <text x={cx} y={cy + 44} textAnchor="middle" className="fill-ink-3 text-[9.5px] italic">out of scope</text>}
          </g>
        );
      })}
    </svg>
  );
}
