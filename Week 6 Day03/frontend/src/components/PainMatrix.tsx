// Pain points placed by how often they happen (x) and how much they hurt (y).
import type { Finding } from "../api";

const W = 360, H = 300, P = 34;
const x = (v: number) => P + ((v - 0.5) / 5) * (W - P - 10);
const y = (v: number) => H - P - ((v - 0.5) / 5) * (H - P - 10);

export default function PainMatrix({ findings }: { findings: Finding[] }) {
  const pts = findings.filter((f) => f.kind === "pain_point" && f.frequency && f.impact && f.review !== "wrong");
  // nudge points that share a cell so labels stay readable
  const seen: Record<string, number> = {};
  return (
    <svg data-testid="pain-matrix" viewBox={`0 0 ${W} ${H}`} className="w-full">
      <rect x={x(3)} y={y(5.5)} width={x(5.5) - x(3)} height={y(3) - y(5.5)} fill="#FDEEE9" rx="6" />
      <text x={x(3) + 6} y={y(5.5) + 14} textAnchor="start" fontSize="10" fontWeight="700" fill="#E8552F">Fix first</text>
      {[1, 2, 3, 4, 5].map((v) => (
        <g key={v}>
          <line x1={x(v)} x2={x(v)} y1={y(0.5)} y2={y(5.5)} stroke="#E6E8F0" />
          <line x1={x(0.5)} x2={x(5.5)} y1={y(v)} y2={y(v)} stroke="#E6E8F0" />
          <text x={x(v)} y={H - P + 14} textAnchor="middle" fontSize="10" fill="#9A9EB3">{v}</text>
          <text x={P - 10} y={y(v) + 3} textAnchor="end" fontSize="10" fill="#9A9EB3">{v}</text>
        </g>
      ))}
      <text x={(W + P) / 2} y={H - 4} textAnchor="middle" fontSize="10.5" fontWeight="600" fill="#5E6378">How often →</text>
      <text x={10} y={(H - P) / 2} textAnchor="middle" fontSize="10.5" fontWeight="600" fill="#5E6378" transform={`rotate(-90 10 ${(H - P) / 2})`}>How much it hurts →</text>
      {pts.map((f) => {
        const key = `${f.frequency}-${f.impact}`;
        const n = (seen[key] = (seen[key] ?? -1) + 1);
        const cx = x(f.frequency!) - n * 22, cy = y(f.impact!) + n * 16;
        const bad = f.evidence_ok === false;
        return (
          <g key={f.id} data-testid={`pain-${f.id}`}>
            <circle cx={cx} cy={cy} r="12" fill={bad ? "#FFFFFF" : "#E8552F"} stroke={bad ? "#E8552F" : "#FFFFFF"} strokeWidth="2" strokeDasharray={bad ? "3 2" : undefined} opacity="0.95" />
            <text x={cx} y={cy + 3.5} textAnchor="middle" fontSize="9.5" fontWeight="700" fill={bad ? "#E8552F" : "#FFFFFF"}>{f.id}</text>
          </g>
        );
      })}
    </svg>
  );
}
