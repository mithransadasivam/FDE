// Ask the data: the bank's people ask CaseFlow a question in plain English (Day 7). The client's screen.
// The model writes one query; the validator checks it, row security limits it to what this person may see, then it runs.
import { AlertTriangle, Ban, CheckCircle2, ChevronRight, Database, Loader2, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type Answer7, type DataStatus } from "../api";
import { Button, Card, Chip, NotBuilt } from "../components/ui";
import { ResultTable, Sql, UserCard, fmt } from "./data/shared";

const USER_KEY = "fde.data.user";

function StatusChip({ a }: { a: Answer7 }) {
  if (a.status === "answered") return <Chip tone="teal"><CheckCircle2 size={11} /> Answered{a.attempts.length > 1 ? " after one repair" : ""}</Chip>;
  if (a.status === "cannot_answer") return <Chip tone="amber"><AlertTriangle size={11} /> Cannot answer</Chip>;
  if (a.status === "refused") return <Chip tone="ember"><Ban size={11} /> Refused</Chip>;
  return <Chip tone="ember"><AlertTriangle size={11} /> The query failed</Chip>;
}

export default function AskData() {
  const [st, setSt] = useState<DataStatus | null>(null);
  const [user, setUser] = useState(() => { try { return localStorage.getItem(USER_KEY) || "tom.reyes"; } catch { return "tom.reyes"; } });
  const [tips, setTips] = useState<{ id: string; question: string }[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<Answer7 | null>(null);
  const [err, setErr] = useState("");
  const [nb, setNb] = useState("");
  const [showRun, setShowRun] = useState(false);
  useEffect(() => { api.get<DataStatus>("/api/data/status").then(setSt); }, []);
  useEffect(() => {
    try { localStorage.setItem(USER_KEY, user); } catch { /* private window */ }
    api.get<{ id: string; question: string }[]>(`/api/data/suggestions?user=${user}`).then(setTips);
    setAns(null); setErr("");
  }, [user]);
  if (!st) return null;
  const ask = async (q = text) => {
    if (!q.trim()) return;
    setText(q); setBusy(true); setErr(""); setNb(""); setShowRun(false);
    try { setAns(await api.post<Answer7>("/api/data/ask", { question: q, user })); }
    catch (e) {
      setAns(null);
      if (e instanceof ApiError && e.status === 501) setNb(e.message);
      else setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };
  const me = st.users.find((u) => u.id === user);
  const last = ans?.attempts[ans.attempts.length - 1];
  const single = ans && ans.status === "answered" && ans.rows.length === 1 && ans.rows[0].length === 1;
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">Client workspace <ChevronRight size={13} /> <span className="text-ink-2">Ask the data</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Ask the data: CaseFlow</h1>
      <div className="text-[12.5px] text-ink-2">
        Every application with a manual review, May 2025 to {new Date(st.as_of).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}. Semantic layer <span className="font-mono">{st.layer}</span>.
        You see only what your role allows: that is enforced on every query, not asked of the model.
      </div>

      <div className="mt-4 grid grid-cols-[300px_1fr] gap-4">
        <div className="space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">Signed in as</div>
          {st.users.map((u) => <UserCard key={u.id} u={u} active={u.id === user} onClick={() => setUser(u.id)} />)}
        </div>

        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex gap-2">
              <input data-testid="ask-input" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()}
                placeholder={`Ask a question, ${me?.name.split(" ")[0] ?? ""}`}
                className="flex-1 rounded-lg border border-black/10 px-3 py-2 text-[13.5px] outline-none focus:border-navy" />
              <Button onClick={() => ask()} disabled={busy || !text.trim()} testId="ask-go">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Ask
              </Button>
            </div>
            <div className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-ink-3">{st.fake ? "Questions the scripted model knows" : "Try one of these"}</div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {tips.map((t) => (
                <button key={t.id} data-testid={`suggest-${t.id}`} onClick={() => ask(t.question)}
                  className="rounded-full border border-black/[0.08] bg-mist px-2.5 py-1 text-left text-[12px] text-ink-2 hover:border-navy hover:text-ink">{t.question}</button>
              ))}
            </div>
          </Card>

          {nb && <NotBuilt ticket={nb.includes("ENG-702") ? "ENG-702" : "ENG-701"}>{nb}. No query runs until it has been checked: open docs/tickets/{nb.includes("ENG-702") ? "ENG-702" : "ENG-701"}.md.</NotBuilt>}
          {err && <Card className="border-ember/30 bg-ember-50 p-4 text-[12.5px] text-ember" testId="ask-error">{err}</Card>}

          {ans && (
            <Card className="p-4" testId="answer">
              <div className="flex items-center justify-between gap-3">
                <div className="text-[14px] font-semibold">{ans.question}</div>
                <StatusChip a={ans} />
              </div>
              <div className="mt-1 flex items-center gap-1.5 text-[11.5px] text-teal" data-testid="answer-scope"><ShieldCheck size={12} /> Row security: {ans.scope}</div>

              <div className="mt-3">
                {ans.status === "answered" && single && (
                  <div data-testid="answer-value" className="text-[34px] font-semibold tracking-tight">{fmt(ans.rows[0][0])}
                    <span className="ml-2 text-[13px] font-normal text-ink-3">{ans.columns[0]}</span></div>
                )}
                {ans.status === "answered" && !single && <ResultTable columns={ans.columns} rows={ans.rows} testId="answer-table" />}
                {ans.status === "cannot_answer" && <div data-testid="answer-cannot" className="rounded-lg bg-amber-50 px-3 py-2 text-[13px] text-ink">{ans.cannot_answer}</div>}
                {(ans.status === "refused" || ans.status === "error") && (
                  <div data-testid="answer-refused" className="rounded-lg bg-ember-50 px-3 py-2 text-[13px] text-ink">
                    No answer: {last?.check.reasons.join("; ") || last?.error}. The agent had one more try and could not fix it.
                  </div>
                )}
                {ans.capped && <div className="mt-1.5 text-[11.5px] text-amber">Only the first {ans.rows.length.toLocaleString()} rows: the row limit.</div>}
              </div>

              {ans.explanation && <div className="mt-3 text-[12.5px] text-ink-2">{ans.explanation}</div>}
              {ans.assumptions.length > 0 && (
                <div className="mt-3 rounded-lg border border-amber/30 bg-amber-50/60 px-3 py-2" data-testid="answer-assumptions">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-amber">What the agent assumed</div>
                  <ul className="mt-1 list-disc pl-4 text-[12.5px] text-ink">{ans.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
                </div>
              )}

              <div className="mt-4 border-t border-black/[0.06] pt-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[12.5px] font-semibold"><Database size={13} /> How it was answered</div>
                  {ans.attempts.some((a) => a.secured_sql) && (
                    <Button variant="ghost" onClick={() => setShowRun(!showRun)} testId="show-secured">{showRun ? "Hide" : "Show"} the query that ran</Button>
                  )}
                </div>
                <div className="mt-2 space-y-3">
                  {ans.attempts.map((a, i) => (
                    <div key={i} data-testid={`attempt-${i + 1}`}>
                      <div className="mb-1 flex flex-wrap items-center gap-1.5 text-[11.5px]">
                        <span className="font-semibold">{i === 0 ? "The model's query" : <span className="inline-flex items-center gap-1"><RefreshCw size={11} /> The repair</span>}</span>
                        {a.check.ok ? <Chip tone="teal">Checked: read-only, approved tables</Chip> : a.check.reasons.map((r) => <Chip key={r} tone="ember">{r}</Chip>)}
                        {a.check.notes.map((n) => <Chip key={n} tone="mist">{n}</Chip>)}
                        {a.error && <Chip tone="ember">{a.error}</Chip>}
                      </div>
                      <Sql sql={a.sql} tone={a.check.ok && !a.error ? "plain" : "refused"} />
                      {showRun && a.secured_sql && (
                        <div className="mt-1.5" data-testid={`secured-${i + 1}`}>
                          <div className="mb-1 text-[11.5px] font-semibold text-teal">What ran, after row security for {me?.name}</div>
                          <Sql sql={a.secured_sql} tone="secured" />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <div className="mt-2 text-[11px] text-ink-3">{ans.tokens_in.toLocaleString()} tokens in, {ans.tokens_out} out · {ans.layer}</div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
