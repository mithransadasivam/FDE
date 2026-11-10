import { Plus, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Criterion, type UseCase } from "../../api";
import CriterionCard from "../../components/CriterionCard";
import UseCaseMatrix from "../../components/UseCaseMatrix";
import { Button, Card, Chip } from "../../components/ui";

const blank = (id: string): Criterion => ({
  id, name: "New criterion", kind: "guardrail", metric: "", baseline: null, target: null, unit: "",
  direction: "increase", measured_how: "", owner: "", by_when: "", problems: [],
});

function Score({ label, v, onSet }: { label: string; v: number; onSet: (n: number) => void }) {
  return (
    <div className="flex items-center gap-[2px]">
      <span className="w-[40px] text-[10.5px] text-ink-3">{label}</span>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} onClick={() => onSet(n)} className={`h-[15px] w-[15px] rounded-sm text-[9px] font-bold ${n <= v ? "bg-navy text-white" : "bg-mist text-ink-3"}`}>{n}</button>
      ))}
    </div>
  );
}

export default function SuccessTab({ onChange }: { onChange: () => void }) {
  const [cs, setCs] = useState<Criterion[]>([]);
  const [us, setUs] = useState<UseCase[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get<Criterion[]>("/api/criteria").then(setCs).catch((e) => setError(e.message));
    api.get<UseCase[]>("/api/usecases").then(setUs);
  }, []);

  const save = async (c: Criterion) => { setCs(await api.put<Criterion[]>(`/api/criteria/${c.id}`, c)); onChange(); };
  const del = async (id: string) => { setCs(await api.del<Criterion[]>(`/api/criteria/${id}`)); onChange(); };
  const add = () => {
    const n = Math.max(0, ...cs.map((c) => Number(c.id.replace(/\D/g, "")) || 0)) + 1;
    save(blank(`SC${n}`));
  };
  const editUc = async (u: UseCase, change: Partial<UseCase>) => {
    try { setUs(await api.put<UseCase[]>(`/api/usecases/${u.id}`, change)); onChange(); setError(""); }
    catch (e) { setError((e as Error).message); }
  };
  const measurable = cs.filter((c) => c.problems.length === 0).length;
  const ranked = [...us].sort((a, b) => b.score - a.score);

  return (
    <div className="grid grid-cols-[1fr_520px] gap-4">
      <div>
        <div className="mb-2 flex items-center justify-between px-1">
          <div>
            <div className="text-[14px] font-semibold">Success criteria</div>
            <div className="text-[12px] text-ink-3"><span data-testid="measurable-count">{measurable} of {cs.length}</span> measurable · business, quality and guardrail</div>
          </div>
          <Button variant="secondary" onClick={add} testId="add-criterion"><Plus size={14} /> Add criterion</Button>
        </div>
        {error && <div className="mb-2 rounded-lg bg-ember-50 px-4 py-2 text-[12.5px] text-ember">{error}</div>}
        <div className="grid grid-cols-2 gap-3">
          {cs.map((c) => <CriterionCard key={c.id + JSON.stringify(c)} c={c} onSave={save} onDelete={del} />)}
        </div>
      </div>
      <div className="space-y-3">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div className="text-[14px] font-semibold">First use case</div>
            <div className="flex gap-2 text-[10.5px] text-ink-3">
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-teal" />low risk</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber" />medium</span>
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-ember" />high</span>
            </div>
          </div>
          <UseCaseMatrix useCases={us} onPick={(u) => editUc(u, { first_choice: true })} />
        </Card>
        <Card className="divide-y divide-black/[0.05]">
          {ranked.map((u) => (
            <div key={u.id} data-testid={`uc-row-${u.id}`} className={`flex items-center gap-3 px-4 py-2.5 ${u.first_choice ? "bg-ember-50/60" : ""}`}>
              <div className="w-10 text-center"><div className="text-[15px] font-semibold">{u.score}</div><div className="text-[9.5px] text-ink-3">score</div></div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-[12.5px] font-semibold">{u.id} · {u.name} {u.first_choice && <Chip tone="ember"><Star size={10} className="fill-ember" /> first</Chip>}</div>
                {u.excluded_reason ? <div className="text-[11.5px] text-ember">Out of scope: {u.excluded_reason}</div>
                  : <div className="mt-1 flex gap-2.5"><Score label="value" v={u.value} onSet={(n) => editUc(u, { value: n })} /><Score label="feasible" v={u.feasibility} onSet={(n) => editUc(u, { feasibility: n })} /><Score label="risk" v={u.risk} onSet={(n) => editUc(u, { risk: n })} /></div>}
              </div>
              {!u.excluded_reason && !u.first_choice && <button data-testid={`pick-${u.id}`} aria-label="choose as first use case" title="Choose as first use case" onClick={() => editUc(u, { first_choice: true })} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-black/10 text-ink-3 hover:border-ember hover:text-ember"><Star size={14} /></button>}
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
