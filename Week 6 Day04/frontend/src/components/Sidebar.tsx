// The console's navigation. Screens arrive day by day; later ones show the day they are built.
import {
  Activity, BarChart3, Bot, Briefcase, Compass, Database, FlaskConical, GitBranch, Inbox,
  PackageCheck, PenTool, Sparkles, Waypoints,
} from "lucide-react";

const WORKSPACE = [
  { label: "Cases", icon: Briefcase, day: 3, page: "cases" },
  { label: "Review queue", icon: Inbox, day: 6 },
  { label: "Ask the data", icon: Database, day: 7 },
  { label: "Workflows", icon: GitBranch, day: 10 },
];
const CONTROL = [
  { label: "Discovery", icon: Compass, day: 1, page: "discovery" },
  { label: "Design & cost", icon: PenTool, day: 2, page: "design" },
  { label: "Evaluation", icon: FlaskConical, day: 4, page: "evaluation" },
  { label: "Agent runs", icon: Bot, day: 9 },
  { label: "Model lab", icon: Sparkles, day: 11 },
  { label: "Operations", icon: Activity, day: 12 },
  { label: "Value", icon: BarChart3, day: 13 },
  { label: "Handover", icon: PackageCheck, day: 14 },
];
const STAGES = ["Discover", "Prototype", "Pilot", "Production", "Handover"];
const STAGE = 1; // Days 3–4: prototype
export const COURSE_DAY = 4;

function Item({ label, icon: I, day, active, page }: { label: string; icon: any; day: number; active?: boolean; page?: string }) {
  const ready = day <= COURSE_DAY && !!page;
  return (
    <div data-testid={`nav-${page ?? label}`} onClick={() => ready && (window.location.hash = `#/${page}`)}
      className={`flex items-center gap-3 rounded-lg px-3 py-[7px] text-[13px] ${ready ? "cursor-pointer hover:bg-white/5" : ""} ${active ? "bg-white/10 text-white" : ready ? "text-white/75" : "text-white/35"}`}>
      <I size={15} className={active ? "text-[#5FD3C1]" : ""} />
      <span className="flex-1">{label}</span>
      <span className={`text-[10px] ${active ? "text-[#5FD3C1]" : "text-white/30"}`}>D{day}</span>
    </div>
  );
}

export default function Sidebar({ fake, page }: { fake: boolean | null; page: string }) {
  return (
    <aside className="flex w-[236px] shrink-0 flex-col bg-navy px-3 py-4">
      <div className="flex items-center gap-2.5 px-2">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-teal"><Waypoints size={17} className="text-white" /></div>
        <div>
          <div className="text-[14px] font-semibold text-white">Engagement Console</div>
          <div className="text-[11.5px] text-white/50">Kestrelmoor Bank · KYC</div>
        </div>
      </div>
      <div className="mt-6 px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/35">Client workspace</div>
      <div className="mt-1.5 space-y-0.5">{WORKSPACE.map((n) => <Item key={n.label} {...n} active={(n as { page?: string }).page === page} />)}</div>
      <div className="mt-5 px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/35">FDE control room</div>
      <div className="mt-1.5 space-y-0.5">{CONTROL.map((n) => <Item key={n.label} {...n} active={(n as { page?: string }).page === page} />)}</div>
      <div className="mt-auto rounded-xl bg-white/[0.06] p-3">
        <div className="text-[11.5px] font-semibold text-white">Engagement · week 1 of 6 · day {COURSE_DAY}</div>
        <div className="mt-2.5 flex gap-1">
          {STAGES.map((s, i) => <div key={s} className={`h-1.5 flex-1 rounded-full ${i < STAGE ? "bg-[#5FD3C1]" : i === STAGE ? "bg-ember" : "bg-white/15"}`} />)}
        </div>
        <div className="mt-1.5 flex justify-between text-[10px] text-white/45"><span className="text-white/80">{STAGES[STAGE]}</span><span>Handover</span></div>
        <div className="mt-3 flex items-center gap-1.5 text-[11px] text-white/60">
          <span className={`h-2 w-2 rounded-full ${fake ? "bg-amber" : "bg-[#5FD3C1]"}`} />
          {fake === null ? "Connecting…" : fake ? "Scripted model (test mode)" : "Model: OpenRouter"}
        </div>
      </div>
    </aside>
  );
}
