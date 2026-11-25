// Row security: the same queries as Tom, Grace and Helen (ENG-702), and one question asked by all three.
import { CheckCircle2, Loader2, Play, ShieldCheck, Users, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Answer7, type RowCheckView } from "../../api";
import { Button, Card, Kpi, NotBuilt } from "../../components/ui";
import { brief } from "./shared";

const SAME = [
  { id: "Q10", text: "What is our backlog right now?" },
  { id: "X03", text: "List five customers whose applications were declined in October 2026." },
];

export default function RowSecurityTab() {
  const [v, setV] = useState<RowCheckView | null>(null);
  const [q, setQ] = useState(SAME[0].text);
  const [same, setSame] = useState<Record<string, Answer7 | string>>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get<RowCheckView>("/api/data/rowchecks").then(setV); }, []);
  if (!v) return null;
  const askAll = async () => {
    setBusy(true);
    const out: Record<string, Answer7 | string> = {};
    for (const u of v.users) {
      try { out[u.id] = await api.post<Answer7>("/api/data/ask", { question: q, user: u.id }); }
      catch (e) { out[u.id] = e instanceof ApiError ? e.message : String(e); }
    }
    setSame(out); setBusy(false);
  };
  const s = v.summary;
  return (
    <div className="space-y-4">
      {v.not_built && <NotBuilt ticket="ENG-702">{v.not_built}. Until row security is built, every query is refused: open docs/tickets/ENG-702.md.</NotBuilt>}
      <div className="grid grid-cols-4 gap-3">
        {v.users.map((u) => (
          <Card key={u.id} className="px-4 py-3">
            <div className="text-[13px] font-semibold">{u.name}</div>
            <div className="text-[11.5px] text-ink-2">{u.title} · role <span className="font-mono">{u.role}</span></div>
            <div className="mt-1 flex items-center gap-1 text-[11.5px] text-teal"><ShieldCheck size={12} /> {u.scope}</div>
          </Card>
        ))}
        {s ? <Kpi label="Checks as expected" value={`${s.passed} of ${s.total}`} tone={s.leaks ? "ember" : "teal"} sub={s.leaks ? `${s.leaks} leaks or wrong results` : "no leaks"} />
          : <Kpi label="Checks as expected" value="—" />}
      </div>

      <Card className="overflow-hidden" testId="rls-table">
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 text-[13.5px] font-semibold"><Users size={15} /> The same query, as each person</div>
          <div className="text-[12px] text-ink-2">From data/Day07_Slide15_row_checks.json. Each query is written as if by the model, then checked and secured for the person.</div>
        </div>
        <table className="w-full text-left text-[12.5px]">
          <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
            <tr><th className="px-4 py-1.5">#</th><th>What it tries</th><th>The query</th>{v.users.map((u) => <th key={u.id} className="pr-3">{u.name}</th>)}</tr>
          </thead>
          <tbody>
            {v.checks.map((c) => (
              <tr key={c.id} data-testid={`rls-${c.id}`} className="border-t border-black/[0.05] align-top">
                <td className="px-4 py-2 text-ink-3">{c.id}</td>
                <td className="py-2 pr-3 font-semibold">{c.what}</td>
                <td className="max-w-[300px] py-2 pr-3 font-mono text-[11px] text-ink-2">{c.sql}</td>
                {v.users.map((u) => {
                  const r = c.results[u.id];
                  return (
                    <td key={u.id} className="py-2 pr-3 text-[12px]">
                      {!r ? <span className="text-ink-3">expected {brief(c.expected[u.id], 2)}</span> : (
                        <span className={`inline-flex items-start gap-1 ${r.passed ? "" : "font-semibold text-ember"}`}>
                          {r.passed ? <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-teal" /> : <XCircle size={13} className="mt-0.5 shrink-0" />}
                          <span>{r.error || brief(r.rows, 2)}{!r.passed && !r.error && <span className="block font-normal text-ink-3">expected {brief(r.expected, 2)}</span>}</span>
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card className="p-4" testId="same-question">
        <div className="text-[13.5px] font-semibold">One question, three people</div>
        <div className="text-[12px] text-ink-2">The model writes the same query for all three. Row security, not the model, makes the answers different.</div>
        <div className="mt-2 flex gap-2">
          <select data-testid="same-q" value={q} onChange={(e) => { setQ(e.target.value); setSame({}); }} className="flex-1 rounded-lg border border-black/10 bg-white px-2 py-1.5 text-[12.5px]">
            {SAME.map((x) => <option key={x.id} value={x.text}>{x.text}</option>)}
          </select>
          <Button onClick={askAll} disabled={busy} testId="same-go">{busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Ask as all three</Button>
        </div>
        {Object.keys(same).length > 0 && (
          <div className="mt-3 grid grid-cols-3 gap-3">
            {v.users.map((u) => {
              const a = same[u.id];
              return (
                <div key={u.id} data-testid={`same-${u.id}`} className="rounded-lg border border-black/[0.06] px-3 py-2">
                  <div className="text-[12.5px] font-semibold">{u.name}</div>
                  {typeof a === "string" ? <div className="mt-1 text-[12px] text-ember">{a}</div> : (
                    <>
                      <div className="mt-1 text-[20px] font-semibold leading-tight">{a.rows.length === 1 && a.rows[0].length === 1 ? brief(a.rows) : `${a.rows.length} rows`}</div>
                      {!(a.rows.length === 1 && a.rows[0].length === 1) && <div className="mt-1 text-[11.5px] text-ink-2">{brief(a.rows.map((r) => r.slice(0, 2)), 3)}</div>}
                      <div className="mt-1 text-[11px] text-teal">{a.scope}</div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
