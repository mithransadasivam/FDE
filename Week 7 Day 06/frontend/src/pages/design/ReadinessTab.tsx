import { Database, Loader2, ScanSearch, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, type ProfileResult } from "../../api";
import { Button, Card, NotBuilt } from "../../components/ui";

const TONE = {
  green: { dot: "bg-teal", text: "text-teal", bg: "bg-teal-50" },
  amber: { dot: "bg-amber", text: "text-amber", bg: "bg-amber-50" },
  red: { dot: "bg-ember", text: "text-ember", bg: "bg-ember-50" },
};
const level = (pct: number) => (pct <= 2 ? "green" : pct <= 10 ? "amber" : "red");

function Cell({ pct, testId }: { pct: number; testId?: string }) {
  const t = TONE[level(pct)];
  return <td data-testid={testId} className="px-2 py-1.5"><span className={`inline-block min-w-[52px] rounded-md px-2 py-0.5 text-center text-[12px] font-semibold tabular-nums ${pct === 0 ? "bg-mist text-ink-3" : `${t.bg} ${t.text}`}`}>{pct}%</span></td>;
}

export default function ReadinessTab() {
  const [res, setRes] = useState<ProfileResult | null>(null);
  const [info, setInfo] = useState<{ file: string; rows: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notBuilt, setNotBuilt] = useState("");
  useEffect(() => {
    api.get<{ file: string; rows: number }>("/api/design/sample").then(setInfo);
    api.get<ProfileResult | null>("/api/design/profile").then((r) => r && setRes(r));
  }, []);
  const run = async () => {
    setBusy(true); setNotBuilt("");
    try { setRes(await api.post<ProfileResult>("/api/design/profile")); }
    catch (e) { if (e instanceof ApiError && e.status === 501) setNotBuilt(e.message); else throw e; }
    finally { setBusy(false); }
  };
  const issues = res?.profiles.filter((p) => p.issues.length) ?? [];

  return (
    <div>
      <Card className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-mist"><Database size={17} className="text-ink-2" /></div>
          <div>
            <div className="text-[14px] font-semibold">CaseFlow sample export: proof-of-address reviews</div>
            <div className="text-[12.5px] text-ink-2">{info ? `${info.file} · ${info.rows} rows · checked against data/Day02_Slide10_data_dictionary.csv` : "…"}</div>
          </div>
        </div>
        <Button onClick={run} disabled={busy} testId="run-profile">{busy ? <Loader2 size={14} className="animate-spin" /> : <ScanSearch size={14} />} {res ? "Profile again" : "Profile the sample"}</Button>
      </Card>
      {notBuilt && <div className="mt-3"><NotBuilt ticket="ENG-201">{notBuilt}. Open docs/tickets/ENG-201.md.</NotBuilt></div>}
      {res && (
        <>
          <div className="mt-4 grid grid-cols-4 gap-3" data-testid="readiness">
            {res.readiness.map((r) => {
              const t = TONE[r.status];
              return (
                <Card key={r.name} testId={`ready-${r.name}`} className={`p-4 ${r.status === "red" ? "border-ember/50" : ""}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-semibold">{r.name}</span>
                    <span data-testid="status" data-status={r.status} className={`flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-bold uppercase ${t.bg} ${t.text}`}><span className={`h-2 w-2 rounded-full ${t.dot}`} />{r.status}</span>
                  </div>
                  <div className={`mt-2 text-[26px] font-semibold leading-none ${t.text}`}>{r.value}</div>
                  <div className="mt-1.5 text-[12px] text-ink-2">{r.detail}</div>
                </Card>
              );
            })}
          </div>
          <div className="mt-4 grid grid-cols-[1fr_380px] gap-4">
            <Card className="overflow-hidden">
              <table className="w-full text-left text-[12.5px]" data-testid="profile-table">
                <thead className="bg-navy text-[11.5px] text-white">
                  <tr><th className="px-3 py-2">Column</th><th className="px-2">Missing</th><th className="px-2">Wrong format</th><th className="px-2">Distinct</th><th className="px-2">Personal data</th><th className="px-2">Examples of bad values</th></tr>
                </thead>
                <tbody>
                  {res.profiles.map((p, i) => {
                    const pii = Object.entries(p.pii_found);
                    return (
                      <tr key={p.column} data-testid={`col-${p.column}`} className={i % 2 ? "bg-mist/50" : ""}>
                        <td className="px-3 py-1.5 font-mono text-[12px] font-semibold">{p.column}</td>
                        <Cell pct={p.missing_pct} />
                        <Cell pct={p.invalid_pct} />
                        <td className="px-2 text-ink-2 tabular-nums">{p.distinct}</td>
                        <td className="px-2" data-testid="pii">{pii.length ? <span className="inline-flex items-center gap-1 rounded-md bg-ember px-2 py-0.5 text-[11px] font-bold text-white"><ShieldAlert size={11} />{pii.map(([k, n]) => `${k} ${n}`).join(" · ")}</span> : <span className="text-ink-3">–</span>}</td>
                        <td className="px-2 font-mono text-[11.5px] text-ink-2">{p.bad_examples.join(", ")}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
            <Card className="p-4">
              <div className="text-[14px] font-semibold">Issues to take to the client</div>
              <div className="text-[12px] text-ink-3">Some are real problems, some are expected. Decide which.</div>
              <div className="mt-3 space-y-2.5" data-testid="issues">
                {issues.map((p) => (
                  <div key={p.column} className="rounded-lg bg-mist px-3 py-2">
                    <div className="font-mono text-[12px] font-semibold">{p.column}</div>
                    {p.issues.map((t) => <div key={t} className={`text-[12px] ${t.startsWith("undeclared") ? "font-semibold text-ember" : "text-ink-2"}`}>{t}</div>)}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
