// Crashes and writes: arm a crash at a named point, see the worker die and come back, and check every write the workflow makes.
import { Zap } from "lucide-react";
import { useState } from "react";
import { api } from "../../api";
import { Button, Card, Chip } from "../../components/ui";
import { WorkerBar, useWorkflowStatus } from "./parts";

export default function CrashTab() {
  const st = useWorkflowStatus(1000);
  const [ticket, setTicket] = useState("KX-1004");
  const arm = async (point: string) => { await api.post("/api/workflow/crash", { point, ticket: point === "now" ? "*" : ticket }); };
  if (!st) return null;
  const w = st.worker;
  return (
    <div className="space-y-4">
      <WorkerBar st={st} />
      <div className="grid grid-cols-[1fr_380px] gap-4">
        <Card className="overflow-hidden" testId="crash-points">
          <div className="flex items-center gap-3 px-4 py-3">
            <div className="flex-1"><div className="text-[13.5px] font-semibold">Crash points</div>
              <div className="text-[12px] text-ink-2">Arm one, then run the case: the worker dies there, as in a real crash, and npm run dev starts it again. data/Day10_Slide15_crash_points.csv</div></div>
            <label className="text-[12px] text-ink-2">for <select data-testid="crash-ticket" value={ticket} onChange={(e) => setTicket(e.target.value)} className="ml-1 h-8 rounded-lg border border-black/10 bg-white px-2 text-[12px]">
              {["KX-1001", "KX-1002", "KX-1003", "KX-1004"].map((t) => <option key={t}>{t}</option>)}</select></label>
          </div>
          <table className="w-full text-left text-[12px]">
            <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Point</th><th>Where</th><th>Before the fix</th><th>After the fix</th><th className="w-[90px]" /></tr></thead>
            <tbody>{w.points.map((p) => (
              <tr key={p.point} className="border-t border-black/[0.05] align-top">
                <td className="px-4 py-2 font-mono text-[11.5px] font-semibold">{p.point}<div className="font-sans text-[11px] font-normal text-ink-3">{p.use_with}</div></td>
                <td className="py-2 pr-2 text-ink-2">{p.where}</td><td className="py-2 pr-2">{p.before_the_fix}</td><td className="py-2 pr-2 text-teal">{p.after_the_fix}</td>
                <td className="py-2 pr-4">{p.point !== "now" && <Button testId={`arm-${p.point}`} variant="secondary" onClick={() => arm(p.point)}><Zap size={12} /> Arm</Button>}</td>
              </tr>))}</tbody>
          </table>
        </Card>
        <Card className="overflow-hidden" testId="crash-log">
          <div className="px-4 py-3 text-[13.5px] font-semibold">Crashes so far</div>
          <table className="w-full text-left text-[12px]"><tbody>
            {w.crashes.map((c, i) => <tr key={i} className="border-t border-black/[0.05]"><td className="px-4 py-1.5 font-mono text-[11px] text-ink-3">{new Date(c.at * 1000).toLocaleTimeString()}</td>
              <td className="font-mono text-[11.5px]">{c.point}</td><td className="font-mono text-[11.5px]">{c.ticket}</td><td className="pr-4 text-[11px] text-ink-3">pid {c.pid}</td></tr>)}
            {!w.crashes.length && <tr><td className="border-t border-black/[0.05] px-4 py-3 text-ink-3">No crash yet.</td></tr>}
          </tbody></table>
        </Card>
      </div>
      <Card className="overflow-hidden" testId="writes-table">
        <div className="px-4 py-3"><div className="text-[13.5px] font-semibold">Every write the case workflow makes, and how it is made safe to make twice</div>
          <div className="text-[12px] text-ink-2">A step that was cut off runs again from its start. Agreed with Helen Achebe: data/Day10_Slide21_writes.csv</div></div>
        <table className="w-full text-left text-[12px]">
          <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3"><tr><th className="px-4 py-1.5">Write</th><th>System</th><th>Step</th><th>Made safe by</th><th>Key or marker</th><th>Why</th></tr></thead>
          <tbody>{st.writes.map((r) => (
            <tr key={r.write} className="border-t border-black/[0.05] align-top"><td className="px-4 py-1.5 font-semibold">{r.write}</td><td>{r.system}</td><td className="font-mono text-[11.5px]">{r.step}</td>
              <td><Chip tone={r.made_safe_by.startsWith("At least") ? "amber" : "teal"}>{r.made_safe_by}</Chip></td><td className="font-mono text-[11px] text-ink-2">{r.key_or_marker}</td><td className="pr-4 text-ink-2">{r.why}</td></tr>))}</tbody>
        </table>
      </Card>
    </div>
  );
}
