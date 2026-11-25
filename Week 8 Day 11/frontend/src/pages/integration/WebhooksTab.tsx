// Webhooks → Slack: the ticketing system calls the console; only genuine, fresh, first deliveries reach the team's channel (ENG-803).
import { BellRing, CheckCircle2, Hash, Loader2, Send, ShieldAlert, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type WebhookProbe, type WebhooksView } from "../../api";
import { Button, Card, Chip, Kpi, NotBuilt } from "../../components/ui";

function SlackMessageView({ m }: { m: WebhooksView["slack"][number]["messages"][number] }) {
  const sec = m.blocks?.[0]?.text?.text ?? m.text;
  const fields: any[] = m.blocks?.[1]?.fields ?? [];
  const ctx = m.blocks?.[2]?.elements?.[0]?.text;
  return (
    <div className="flex gap-2.5 py-2">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-teal text-white"><BellRing size={15} /></div>
      <div className="min-w-0 text-[12.5px]">
        <div><b>KYC exceptions</b> <span className="rounded bg-mist px-1 text-[10px] text-ink-3">APP</span> <span className="text-[11px] text-ink-3">{m.at.slice(11, 16)}</span></div>
        <div className="whitespace-pre-line">{sec.replace(/\*/g, "")}</div>
        {fields.length > 0 && <div className="mt-1 grid grid-cols-2 gap-x-6 gap-y-0.5 text-[12px]">{fields.map((f, i) => <div key={i} className="whitespace-pre-line text-ink-2">{f.text.replace(/\*/g, "")}</div>)}</div>}
        {ctx && <div className="mt-1 text-[11px] text-ink-3">{ctx}</div>}
      </div>
    </div>
  );
}

export default function WebhooksTab() {
  const [v, setV] = useState<WebhooksView | null>(null);
  const [probes, setProbes] = useState<WebhookProbe[] | null>(null);
  const [team, setTeam] = useState("N1");
  const [chan, setChan] = useState("kyc-north");
  const [busy, setBusy] = useState("");
  const load = () => api.get<WebhooksView>("/api/integration/webhooks").then(setV);
  useEffect(() => { load(); }, []);
  if (!v) return null;
  const raise = async () => { setBusy("raise"); try { await api.post("/api/integration/raise-exception", { team_id: team }); await load(); } finally { setBusy(""); } };
  const probe = async () => { setBusy("probe"); try { setProbes((await api.post<{ probes: WebhookProbe[] }>("/api/integration/webhook-probes")).probes); await load(); } finally { setBusy(""); } };
  const channel = v.slack.find((c) => c.name === chan);
  const passed = probes?.filter((p) => p.passed).length ?? 0;
  return (
    <div className="space-y-4">
      {v.not_built && <NotBuilt ticket="ENG-803">{v.not_built}. Until it is built, every delivery is refused with an error: open docs/tickets/ENG-803.md.</NotBuilt>}
      <div className="grid grid-cols-[1fr_1.2fr] gap-4">
        <div className="space-y-4">
          <Card className="p-4" testId="raise">
            <div className="text-[13.5px] font-semibold">A new KYC exception, in the ticketing system</div>
            <div className="text-[12px] text-ink-2">The ticketing system calls POST /api/hooks/kyc-exceptions with a signed event. The console checks it, then posts to the team's Slack channel.</div>
            <div className="mt-3 flex items-center gap-2">
              <select data-testid="raise-team" value={team} onChange={(e) => setTeam(e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1.5 text-[12.5px]">
                {["N1", "N2", "M1", "M2", "S1", "S2"].map((t) => <option key={t}>{t}</option>)}
              </select>
              <Button onClick={raise} disabled={!!busy} testId="raise-go">{busy === "raise" ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Raise an escalation</Button>
            </div>
          </Card>
          <Card className="overflow-hidden" testId="webhook-probes">
            <div className="flex items-center justify-between px-4 py-3">
              <div>
                <div className="flex items-center gap-2 text-[13.5px] font-semibold"><ShieldAlert size={15} /> Six deliveries, one genuine</div>
                <div className="text-[12px] text-ink-2">The address is not secret: anyone can post to it.</div>
              </div>
              <Button variant="secondary" onClick={probe} disabled={!!busy} testId="probes-go">{busy === "probe" && <Loader2 size={13} className="animate-spin" />} Send the six</Button>
            </div>
            {probes && (
              <>
                <div className="px-4 pb-2" data-testid="webhook-summary"><Kpi label="As expected" value={`${passed} of ${probes.length}`} tone={passed === probes.length ? "teal" : "ember"} /></div>
                <table className="w-full text-left text-[12px]">
                  <tbody>
                    {probes.map((p) => (
                      <tr key={p.id} data-testid={`wprobe-${p.id}`} className="border-t border-black/[0.05] align-top">
                        <td className="px-4 py-1.5 text-ink-3">{p.id}</td><td className="py-1.5 pr-2">{p.what}</td>
                        <td className="py-1.5 pr-2"><Chip tone={p.passed ? "teal" : "ember"}>{p.status === 200 ? <CheckCircle2 size={11} /> : <XCircle size={11} />} {p.status}</Chip></td>
                        <td className="py-1.5 pr-4 text-ink-2">{(() => { try { const j = JSON.parse(p.response); return j.detail ?? `received ${j.received}`; } catch { return p.response; } })()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </Card>
          <Card className="overflow-hidden" testId="webhook-log">
            <div className="px-4 py-3 text-[13.5px] font-semibold">What the console did with each delivery</div>
            <table className="w-full text-left text-[12px]">
              <tbody>
                {v.log.slice(0, 8).map((l, i) => (
                  <tr key={i} className="border-t border-black/[0.05]">
                    <td className="px-4 py-1.5 font-mono text-[11px] text-ink-3">{l.at.slice(11)}</td>
                    <td className="py-1.5 pr-2"><Chip tone={l.outcome === "accepted" ? "teal" : "ember"}>{l.outcome}</Chip></td>
                    <td className="py-1.5 pr-4 text-ink-2">{l.outcome === "accepted" ? `${l.ticket} → #${(l.slack ?? []).join(", #")}` : l.reason}</td>
                  </tr>
                ))}
                {v.log.length === 0 && <tr><td className="px-4 py-2 text-ink-3">No deliveries yet.</td></tr>}
              </tbody>
            </table>
          </Card>
        </div>
        <Card className="overflow-hidden" testId="slack">
          <div className="border-b border-black/[0.06] px-4 py-3">
            <div className="text-[13.5px] font-semibold">Slack · the bank's workspace (stand-in)</div>
            <div className="mt-2 flex flex-wrap gap-1">
              {v.slack.map((c) => (
                <button key={c.name} data-testid={`chan-${c.name}`} onClick={() => setChan(c.name)}
                  className={`flex items-center gap-0.5 whitespace-nowrap rounded-md px-2 py-1 text-[12px] ${chan === c.name ? "bg-navy text-white" : "bg-mist text-ink-2"}`}>
                  <Hash size={11} />{c.name} {c.messages.length > 0 && <span className="ml-1 rounded-full bg-ember px-1.5 text-[10px] text-white">{c.messages.length}</span>}
                </button>
              ))}
            </div>
          </div>
          <div className="max-h-[620px] divide-y divide-black/[0.05] overflow-auto px-4" data-testid="slack-messages">
            {channel && channel.messages.length === 0 && <div className="py-6 text-center text-[12.5px] text-ink-3">No messages in #{chan} yet.</div>}
            {channel?.messages.slice().reverse().map((m, i) => <SlackMessageView key={i} m={m} />)}
          </div>
        </Card>
      </div>
    </div>
  );
}
