// Draws an architecture option from its JSON: four lanes, boxes by kind, arrows for data flows.
// Nodes and edges that break a client rule are drawn in red.
import type { ArchNode, Option } from "../api";

const LANES = [
  { id: "client", label: "Bank staff" },
  { id: "bank", label: "Bank network (UK)" },
  { id: "aws", label: "AWS London (eu-west-2)" },
  { id: "external", label: "Outside the bank" },
] as const;
const LW = 240, NW = 192, NH = 50, RH = 74, TOP = 44;
const STYLE: Record<string, { fill: string; stroke: string; text: string }> = {
  person: { fill: "#FDF5E3", stroke: "#D98E04", text: "#1B1F3B" },
  ui: { fill: "#EEF7F5", stroke: "#0E8F7E", text: "#1B1F3B" },
  service: { fill: "#FFFFFF", stroke: "#9A9EB3", text: "#1B1F3B" },
  model: { fill: "#5B6BBF", stroke: "#5B6BBF", text: "#FFFFFF" },
  ocr: { fill: "#30365E", stroke: "#30365E", text: "#FFFFFF" },
  store: { fill: "#F4F5FA", stroke: "#9A9EB3", text: "#1B1F3B" },
  system: { fill: "#E9EBF3", stroke: "#5E6378", text: "#1B1F3B" },
  audit_log: { fill: "#FDF5E3", stroke: "#B7791F", text: "#1B1F3B" },
  decision: { fill: "#FDEEE9", stroke: "#E8552F", text: "#1B1F3B" },
};
const pos = (n: ArchNode) => {
  const lane = LANES.findIndex((l) => l.id === n.lane);
  return { x: lane * LW + (LW - NW) / 2, y: TOP + n.row * RH + 10 };
};

function wrap(label: string, max = 26): string[] {
  const words = label.split(" "); const lines: string[] = []; let cur = "";
  for (const w of words) { if ((cur + " " + w).trim().length > max) { lines.push(cur.trim()); cur = w; } else cur += " " + w; }
  if (cur.trim()) lines.push(cur.trim());
  return lines.slice(0, 2);
}

export default function ArchCanvas({ option }: { option: Option }) {
  const byId = Object.fromEntries(option.nodes.map((n) => [n.id, n]));
  const badNodes = new Set((option.violations ?? []).filter((v) => v.node).map((v) => v.node));
  const badEdges = new Set((option.violations ?? []).filter((v) => v.edge).map((v) => v.edge!.join(">")));
  const rows = Math.max(...option.nodes.map((n) => n.row)) + 1;
  const H = TOP + rows * RH + 16;
  const edgeGeo = option.edges.flatMap((e) => {
    const a = byId[e.source], b = byId[e.target];
    if (!a || !b) return [];
    const pa = pos(a), pb = pos(b);
    const sameLane = a.lane === b.lane;
    const x1 = sameLane ? pa.x + NW : pa.x + (pb.x > pa.x ? NW : 0);
    const y1 = pa.y + NH / 2 + (sameLane ? (pb.y > pa.y ? 8 : -8) : 0);
    const x2 = sameLane ? pb.x + NW : pb.x + (pb.x > pa.x ? 0 : NW);
    const y2 = pb.y + NH / 2 + (sameLane ? (pb.y > pa.y ? -8 : 8) : 0);
    const bulge = 18 + 12 * Math.abs(a.row - b.row);
    const d = sameLane
      ? `M${x1},${y1} C${x1 + bulge},${y1} ${x2 + bulge},${y2} ${x2},${y2}`
      : `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`;
    const mx = sameLane ? x1 + bulge * 0.75 + 4 : (x1 + x2) / 2;
    const my = sameLane ? y1 + (y2 - y1) * 0.3 + 4 : (y1 + y2) / 2;
    return [{ e, d, mx, my, sameLane, bad: badEdges.has(`${e.source}>${e.target}`) }];
  });
  return (
    <svg data-testid="arch-canvas" viewBox={`0 0 ${LW * 4} ${H}`} className="w-full">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9A9EB3" /></marker>
        <marker id="arrbad" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#E8552F" /></marker>
      </defs>
      {LANES.map((l, i) => (
        <g key={l.id}>
          <rect x={i * LW + 4} y={4} width={LW - 8} height={H - 8} rx="10" fill={l.id === "aws" ? "#F1F8F6" : l.id === "external" ? "#FBF3F1" : "#F7F8FB"} />
          <text x={i * LW + LW / 2} y={26} textAnchor="middle" fontSize="12" fontWeight="700" fill={l.id === "external" ? "#E8552F" : "#5E6378"}>{l.label}</text>
        </g>
      ))}
      {edgeGeo.map(({ e, d, bad }, i) => (
        <path key={i} data-testid={`edge-${e.source}-${e.target}`} data-violation={String(bad)} d={d} fill="none" stroke={bad ? "#E8552F" : "#B8BCCC"} strokeWidth={bad ? 2.5 : 1.5} strokeDasharray={bad ? "6 4" : undefined} markerEnd={`url(#${bad ? "arrbad" : "arr"})`} />
      ))}
      {option.nodes.map((n) => {
        const p = pos(n), s = STYLE[n.kind] ?? STYLE.service, bad = badNodes.has(n.id);
        const lines = wrap(n.label);
        return (
          <g key={n.id} data-testid={`node-${n.id}`} data-violation={String(bad)}>
            <rect x={p.x} y={p.y} width={NW} height={NH} rx="9" fill={s.fill} stroke={bad ? "#E8552F" : s.stroke} strokeWidth={bad ? 3 : 1.5} />
            {lines.map((l, i) => (
              <text key={i} x={p.x + NW / 2} y={p.y + NH / 2 + (i - (lines.length - 1) / 2) * 13 + 4} textAnchor="middle" fontSize="11" fontWeight="600" fill={s.text}>{l}</text>
            ))}
            {n.read_only && <text x={p.x + NW - 6} y={p.y + 12} textAnchor="end" fontSize="8.5" fontWeight="700" fill="#5E6378">READ-ONLY</text>}
            {bad && <g><circle cx={p.x + NW - 2} cy={p.y + 2} r="9" fill="#E8552F" /><text x={p.x + NW - 2} y={p.y + 6} textAnchor="middle" fontSize="12" fontWeight="800" fill="#FFF">!</text></g>}
          </g>
        );
      })}
      {edgeGeo.map(({ e, mx, my, sameLane, bad }, i) => (
        <text key={`l${i}`} x={mx} y={my - 4} textAnchor={sameLane ? "start" : "middle"} fontSize="9.5" fill={bad ? "#E8552F" : "#5E6378"} fontWeight={bad ? 700 : 500} paintOrder="stroke" stroke="#FFFFFF" strokeWidth="4">{e.label}</text>
      ))}
    </svg>
  );
}
