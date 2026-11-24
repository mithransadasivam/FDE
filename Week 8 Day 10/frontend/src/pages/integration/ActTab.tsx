// Act as the person: call the MCP server as Tom, Grace or Helen, and see who the bank's systems think asked (ENG-802).
import { Loader2, Play, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type ActResult, type AuditEntry } from "../../api";
import { Button, Card, Chip } from "../../components/ui";

const PEOPLE = [["tom.reyes", "Tom Reyes", "Analyst · North 1"], ["grace.mensah", "Grace Mensah", "Team lead · North"], ["helen.achebe", "Helen Achebe", "MLRO · all teams"]];
const ACTIONS = [
  { id: "customers", label: "Find every customer I can see", tool: "find_customer", args: { query: "" } },
  { id: "exceptions", label: "List my KYC exceptions", tool: "list_exceptions", args: {} },
  { id: "south", label: "Open a South 1 customer", tool: "get_customer", args: { customer_id: "CU-022478" } },
  { id: "note", label: "Add a note to a North 1 customer", tool: "add_customer_note", args: { customer_id: "CU-022578", text: "Called the applicant about their proof of address" } },
];

export function AuditTable({ entries, testId }: { entries: AuditEntry[]; testId?: string }) {
  return (
    <table className="w-full text-left text-[12px]" data-testid={testId}>
      <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
        <tr><th className="px-3 py-1.5">Time</th><th>System</th><th>Who, as the bank records it</th><th>Action</th><th>Outcome</th></tr>
      </thead>
      <tbody>
        {entries.map((a, i) => (
          <tr key={i} className="border-t border-black/[0.05] align-top">
            <td className="px-3 py-1.5 font-mono text-[11px] text-ink-3">{a.at.slice(11)}</td>
            <td className="py-1.5 pr-2">{a.system}</td>
            <td className="py-1.5 pr-2"><span className={`font-semibold ${a.actor.startsWith("svc-") ? "text-ember" : ""}`}>{a.actor}</span>{a.via && <span className="text-ink-2"> via {a.via}</span>}</td>
            <td className="py-1.5 pr-2">{a.action} <span className="text-ink-3">{a.target}</span></td>
            <td className="py-1.5 pr-3"><Chip tone={a.outcome === "allowed" ? "teal" : "ember"}>{a.outcome}</Chip> <span className="text-[11px] text-ink-2">{a.reason}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ActTab() {
  const [person, setPerson] = useState("tom.reyes");
  const [res, setRes] = useState<ActResult | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [busy, setBusy] = useState("");
  const loadAudit = () => api.get<{ entries: AuditEntry[] }>("/api/integration/audit").then((x) => setAudit(x.entries.slice(0, 12)));
  useEffect(() => { loadAudit(); }, []);
  const run = async (a: (typeof ACTIONS)[number]) => {
    setBusy(a.id);
    try { setRes(await api.post<ActResult>("/api/integration/act", { person, tool: a.tool, args: a.args })); await loadAudit(); }
    finally { setBusy(""); }
  };
  const rows: any[] = res?.ok ? (res.data?.customers ?? res.data?.tickets ?? null) : null;
  const teams = rows ? Array.from(new Set(rows.map((r) => r.team_id))).sort() : [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[320px_1fr] gap-4">
        <Card className="p-4">
          <div className="text-[13.5px] font-semibold">Sign in as</div>
          <div className="text-[12px] text-ink-2">The console signs each course account in with the bank, like a browser would, and calls the MCP server with that token.</div>
          <div className="mt-3 space-y-1.5">
            {PEOPLE.map(([id, n, t]) => (
              <button key={id} data-testid={`act-person-${id}`} onClick={() => { setPerson(id); setRes(null); }}
                className={`flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left ${person === id ? "border-navy bg-navy text-white" : "border-black/[0.06] hover:border-black/20"}`}>
                <UserRound size={14} /><span><span className="block text-[12.5px] font-semibold">{n}</span><span className={`block text-[11px] ${person === id ? "text-white/70" : "text-ink-2"}`}>{t}</span></span>
              </button>
            ))}
          </div>
          <div className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-ink-3">Through the MCP server</div>
          <div className="mt-1.5 space-y-1.5">
            {ACTIONS.map((a) => (
              <Button key={a.id} variant="secondary" onClick={() => run(a)} disabled={!!busy} testId={`act-${a.id}`}>
                {busy === a.id ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} {a.label}
              </Button>
            ))}
          </div>
        </Card>
        <Card className="p-4" testId="act-result">
          {!res ? <div className="text-[12.5px] text-ink-3">Choose a person and an action. The answer comes from the bank's systems, through your MCP server.</div> : (
            <div>
              <div className="flex items-center gap-2 text-[13px]"><span className="font-mono">{res.tool}</span> as <b>{PEOPLE.find((p) => p[0] === res.person)?.[1]}</b>
                {res.ok ? <Chip tone="teal">allowed</Chip> : <Chip tone="ember">refused</Chip>}<span className="text-[11px] text-ink-3">{res.ms} ms</span></div>
              {!res.ok && <div className="mt-2 rounded-lg bg-ember-50 px-3 py-2 text-[12.5px]" data-testid="act-error">{res.error}</div>}
              {rows && (
                <div className="mt-3">
                  <div className="text-[28px] font-semibold" data-testid="act-count">{rows.length}<span className="ml-2 text-[13px] font-normal text-ink-2">{res.data?.customers ? "customers" : "exceptions"}, teams {teams.join(", ")}</span></div>
                  <div className="mt-2 max-h-[230px] overflow-auto rounded-lg border border-black/[0.06]">
                    <table className="w-full text-left text-[12px]"><tbody>
                      {rows.slice(0, 40).map((r) => (
                        <tr key={r.customer_id ?? r.ticket_id} className="border-t border-black/[0.04]">
                          <td className="px-3 py-1 font-mono text-[11px]">{r.customer_id ?? r.ticket_id}</td><td>{r.name ?? r.title}</td><td className="pr-3 text-ink-2">{r.team_id}</td>
                        </tr>))}
                    </tbody></table>
                  </div>
                </div>
              )}
              {res.ok && !rows && <pre className="mt-2 max-h-[260px] overflow-auto rounded-lg bg-mist px-3 py-2 text-[11px]">{JSON.stringify(res.data, null, 2)}</pre>}
            </div>
          )}
        </Card>
      </div>
      <Card className="overflow-hidden" testId="audit">
        <div className="px-4 py-3">
          <div className="text-[13.5px] font-semibold">The bank's audit log: who the CRM and ticketing system think asked</div>
          <div className="text-[12px] text-ink-2">Each system records the token's subject, and “via” the app that acted for them (the token's act claim).</div>
        </div>
        <AuditTable entries={audit} testId="audit-table" />
      </Card>
    </div>
  );
}
