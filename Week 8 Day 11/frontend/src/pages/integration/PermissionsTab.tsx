// Permissions: every tool, as each of the three roles, through the MCP server, against what the bank expects.
import { CheckCircle2, Loader2, Play, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type PermView } from "../../api";
import { Button, Card, Kpi } from "../../components/ui";

const NAMES: Record<string, string> = { "tom.reyes": "Tom · analyst", "grace.mensah": "Grace · team lead", "helen.achebe": "Helen · MLRO" };

export default function PermissionsTab() {
  const [v, setV] = useState<PermView | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get<PermView>("/api/integration/permissions").then(setV); }, []);
  if (!v) return null;
  const run = async () => { setBusy(true); try { setV(await api.post<PermView>("/api/integration/permissions/run")); } finally { setBusy(false); } };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[1fr_auto] items-start gap-4">
        <Card className="p-4">
          <div className="text-[13.5px] font-semibold">The permission matrix</div>
          <div className="text-[12px] text-ink-2">
            Each row is one tool call, made through the MCP server as each person. Expected results are the bank's rules, from data/Day08_Slide26_permission_matrix.csv
            {v.rows.length > 7 ? " and your rows in engagement/integration/permission_rows.json" : ""}.
          </div>
          <div className="mt-3"><Button onClick={run} disabled={busy} testId="perm-run">{busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Run every tool as every person</Button>
            {v.at && <span className="ml-3 text-[11.5px] text-ink-3">Last run {v.at.replace("T", " ")}</span>}</div>
        </Card>
        {v.summary && <div data-testid="perm-summary"><Kpi label="As expected" value={`${v.summary.passed} of ${v.summary.total}`} tone={v.summary.passed === v.summary.total ? "teal" : "ember"}
          sub={v.summary.passed === v.summary.total ? "every cell matches the bank's rules" : `${v.summary.total - v.summary.passed} cells differ`} /></div>}
      </div>
      <Card className="overflow-hidden" testId="perm-table">
        <table className="w-full text-left text-[12.5px]">
          <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
            <tr><th className="px-4 py-1.5">#</th><th>Tool</th><th>What</th>{v.people.map((p) => <th key={p} className="pr-3">{NAMES[p] ?? p}</th>)}<th className="pr-4">The bank's rule</th></tr>
          </thead>
          <tbody>
            {v.rows.map((r) => (
              <tr key={r.id} data-testid={`perm-${r.id}`} className="border-t border-black/[0.05] align-top">
                <td className="px-4 py-2 text-ink-3">{r.id}</td>
                <td className="py-2 pr-2 font-mono text-[11.5px]">{r.tool}</td>
                <td className="py-2 pr-3">{r.what}</td>
                {v.people.map((p) => {
                  const res = v.results[`${r.id}/${p}`];
                  return (
                    <td key={p} className="py-2 pr-3 text-[12px]">
                      <div className="text-ink-3">expected {r[p]}</div>
                      {res && <div className={`flex items-start gap-1 ${res.passed ? "text-teal" : "font-semibold text-ember"}`}>
                        {res.passed ? <CheckCircle2 size={12} className="mt-0.5 shrink-0" /> : <XCircle size={12} className="mt-0.5 shrink-0" />}<span>{res.got}</span></div>}
                    </td>
                  );
                })}
                <td className="py-2 pr-4 text-[11.5px] text-ink-2">{r.rule}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
