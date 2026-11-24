// Sign-in: the bank's sign-in service, the MCP server, how to connect Claude Code, and the token checks (ENG-801).
import { CheckCircle2, Copy, KeyRound, Loader2, LogIn, Server, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type IntStatus, type Me, type TokenProbeView } from "../../api";
import { Button, Card, Chip, Kpi, NotBuilt } from "../../components/ui";

export default function SignInTab() {
  const [st, setSt] = useState<IntStatus | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [p, setP] = useState<TokenProbeView | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => { setBusy(true); api.get<TokenProbeView>("/api/integration/token-probes").then(setP).finally(() => setBusy(false)); };
  useEffect(() => { api.get<IntStatus>("/api/integration/status").then(setSt); api.get<Me>("/api/auth/me").then(setMe); load(); }, []);
  if (!st) return null;
  const meta = st.bank.metadata as Record<string, string> | null;
  const signIn = () => { window.location.href = `/api/auth/login?next=${encodeURIComponent("/#/integrations/signin")}&origin=${encodeURIComponent(window.location.origin)}`; };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4" testId="int-bank">
          <div className="flex items-center gap-2 text-[13.5px] font-semibold"><KeyRound size={15} /> The bank's sign-in service
            {st.bank.up ? <Chip tone="teal">running</Chip> : <Chip tone="ember">not running</Chip>}</div>
          <div className="mt-2 space-y-1 font-mono text-[11px] text-ink-2">
            <div>issuer {meta?.issuer ?? st.bank.url}</div>
            <div>authorize {meta?.authorization_endpoint ?? "—"}</div>
            <div>token {meta?.token_endpoint ?? "—"}</div>
            <div>register {meta?.registration_endpoint ?? "—"}</div>
          </div>
          {!st.bank.up && <div className="mt-2 text-[12px] text-ember">Start it: cd backend && python -m bank.server</div>}
        </Card>
        <Card className="p-4" testId="int-mcp">
          <div className="flex items-center gap-2 text-[13.5px] font-semibold"><Server size={15} /> The FDE's MCP server
            {st.mcp.up ? <Chip tone="teal">running</Chip> : <Chip tone="ember">not running</Chip>}</div>
          <div className="mt-2 font-mono text-[11px] text-ink-2">{st.mcp.url}</div>
          <div className="mt-2 text-[12px] text-ink-2">Without a token it answers 401 and names the bank as the place to sign in (protected resource metadata).</div>
          <div className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-ink-3">Connect Claude Code</div>
          <div className="mt-1 flex items-center gap-2 rounded-lg bg-navy px-2.5 py-1.5 font-mono text-[11px] text-white/90" data-testid="claude-command">
            <span className="flex-1 truncate">{st.claude_command}</span>
            <button onClick={() => navigator.clipboard?.writeText(st.claude_command)} className="text-white/60 hover:text-white"><Copy size={12} /></button>
          </div>
          {!st.mcp.up && <div className="mt-2 text-[12px] text-ember">Start it: cd backend && python -m app.integration.mcp_server</div>}
        </Card>
        <Card className="p-4" testId="int-session">
          <div className="flex items-center gap-2 text-[13.5px] font-semibold"><ShieldCheck size={15} /> This console's sign-in</div>
          {me?.signed_in ? (
            <div className="mt-2 text-[12.5px]">
              <div className="text-[16px] font-semibold" data-testid="me-name">{me.name}</div>
              <div className="text-ink-2">{me.role} · {me.team ?? me.region ?? "all teams"} · {me.scope}</div>
              <div className="mt-1 text-[11.5px] text-ink-3">The token stays on the server; the browser has a session cookie. Ask the data now answers as {me.name?.split(" ")[0]}.</div>
            </div>
          ) : (
            <div className="mt-2">
              <div className="text-[12.5px] text-ink-2">Not signed in. The console signs you in with the bank, as Claude Code does: Authorization Code with PKCE.</div>
              <div className="mt-2"><Button onClick={signIn} testId="sign-in"><LogIn size={13} /> Sign in with the bank</Button></div>
            </div>
          )}
        </Card>
      </div>

      {p?.not_built && <NotBuilt ticket="ENG-801">{p.not_built}. Until it is built, the MCP server refuses every token: open docs/tickets/ENG-801.md.</NotBuilt>}
      {p?.error && <Card className="border-ember/30 bg-ember-50 p-4 text-[12.5px] text-ember">{p.error}</Card>}
      {p && (
        <div className="grid grid-cols-[1.6fr_1fr] gap-4">
          <Card className="overflow-hidden" testId="token-probes">
            <div className="flex items-center justify-between px-4 py-3">
              <div>
                <div className="text-[13.5px] font-semibold">{p.probes.length} tokens, through verify_access_token()</div>
                <div className="text-[12px] text-ink-2">Made by the bank's course helper. The MCP server accepts a token only for <span className="font-mono">{p.audience}</span>.</div>
              </div>
              <div className="flex items-center gap-3">
                {p.summary && <span data-testid="token-summary"><Kpi label="As expected" value={`${p.summary.passed} of ${p.summary.total}`} tone={p.summary.passed === p.summary.total ? "teal" : "ember"} /></span>}
                <Button variant="secondary" onClick={load} disabled={busy}>{busy && <Loader2 size={13} className="animate-spin" />} Check again</Button>
              </div>
            </div>
            <table className="w-full text-left text-[12.5px]">
              <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
                <tr><th className="px-4 py-1.5">#</th><th>The token</th><th>Expected</th><th>Result</th><th className="pr-4">Reason, or who it is</th></tr>
              </thead>
              <tbody>
                {p.probes.map((x) => (
                  <tr key={x.id} data-testid={`tprobe-${x.id}`} className="border-t border-black/[0.05] align-top">
                    <td className="px-4 py-2 text-ink-3">{x.id}</td>
                    <td className="py-2 pr-3">{x.what}<div className="font-mono text-[10.5px] text-ink-3">{x.token_start}</div></td>
                    <td className="py-2 pr-3"><Chip>{x.expect}</Chip></td>
                    <td className="py-2 pr-3">{x.result === null ? <span className="text-ink-3">—</span> :
                      <Chip tone={x.passed ? "teal" : "ember"}>{x.result === "accept" ? <CheckCircle2 size={11} /> : <XCircle size={11} />} {x.result === "accept" ? "accepted" : "refused"}</Chip>}</td>
                    <td className="py-2 pr-4 text-[12px] text-ink-2">{x.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card className="p-4" testId="mcp-checks">
            <div className="text-[13.5px] font-semibold">Tokens the MCP server has checked</div>
            <div className="text-[12px] text-ink-2">From Claude Code, the console and the tests, newest first.</div>
            <div className="mt-2 space-y-1.5">
              {p.checks.length === 0 && <div className="text-[12px] text-ink-3">None yet.</div>}
              {p.checks.map((c, i) => (
                <div key={i} className="flex items-start gap-2 text-[12px]">
                  {c.outcome === "accepted" ? <CheckCircle2 size={13} className="mt-0.5 text-teal" /> : <XCircle size={13} className="mt-0.5 text-ember" />}
                  <span><span className="font-mono text-[11px] text-ink-3">{c.at.slice(11)}</span> {c.who && <b>{c.who} </b>}{c.reason}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
