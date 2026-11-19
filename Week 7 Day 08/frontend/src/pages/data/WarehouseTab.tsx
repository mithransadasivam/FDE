// Warehouse: every table in the client's warehouse, which ones the agent may read, and the semantic layer it is given.
import { BookOpen, CheckCircle2, Lock, Table2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type DataStatus, type LayerView, type WarehouseView } from "../../api";
import { Button, Card, Chip } from "../../components/ui";

export default function WarehouseTab() {
  const [st, setSt] = useState<DataStatus | null>(null);
  const [layer, setLayer] = useState("");
  const [w, setW] = useState<WarehouseView | null>(null);
  const [L, setL] = useState<LayerView | null>(null);
  const [sel, setSel] = useState("caseflow.cases");
  const [view, setView] = useState<"terms" | "yaml">("terms");
  const loadStatus = () => api.get<DataStatus>("/api/data/status").then((s) => { setSt(s); setLayer((x) => x || s.layer); });
  useEffect(() => { loadStatus(); }, []);
  useEffect(() => {
    if (!layer) return;
    api.get<WarehouseView>(`/api/data/warehouse?layer=${layer}`).then(setW);
    api.get<LayerView>(`/api/data/layers/${layer}`).then(setL);
  }, [layer]);
  if (!st || !w || !L) return null;
  const t = w.tables.find((x) => x.table === sel) ?? w.tables[0];
  const approved = w.tables.filter((x) => x.approved);
  const use = async () => { await api.put("/api/data/settings", { layer }); await loadStatus(); };
  return (
    <div className="grid grid-cols-[1.05fr_1fr] gap-4">
      <div className="space-y-4">
        <Card className="overflow-hidden" testId="wh-tables">
          <div className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="flex items-center gap-2 text-[13.5px] font-semibold"><Table2 size={15} /> The warehouse: {w.tables.length} tables, {approved.length} approved</div>
              <div className="text-[12px] text-ink-2">The bank's CaseFlow extract in DuckDB, opened read-only. Only approved tables can be queried.</div>
            </div>
          </div>
          <table className="w-full text-left text-[12.5px]">
            <thead className="bg-mist text-[10.5px] uppercase tracking-wide text-ink-3">
              <tr><th className="px-4 py-1.5">Table</th><th className="text-right">Rows</th><th className="pl-4">Agent</th><th>Row filter</th></tr>
            </thead>
            <tbody>
              {w.tables.map((x) => (
                <tr key={x.table} data-testid={`wh-${x.table}`} onClick={() => setSel(x.table)}
                  className={`cursor-pointer border-t border-black/[0.05] ${sel === x.table ? "bg-amber-50/60" : ""}`}>
                  <td className="px-4 py-2 font-mono text-[12px]">{x.table}</td>
                  <td className="text-right tabular-nums">{x.rows.toLocaleString()}</td>
                  <td className="pl-4">{x.approved ? <Chip tone="teal"><CheckCircle2 size={11} /> Approved</Chip> : <Chip tone="ember"><Lock size={11} /> Not approved</Chip>}</td>
                  <td className="pr-4 text-[11.5px] text-ink-2">{w.row_filters[x.table] ? "by team" : x.approved ? "none" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        {t && (
          <Card className="p-4" testId="wh-columns">
            <div className="text-[13.5px] font-semibold"><span className="font-mono">{t.table}</span></div>
            <div className="text-[12px] text-ink-2">{t.description || (t.approved ? "" : "Not in the semantic layer: the model is never told this table exists.")}</div>
            <table className="mt-2 w-full text-left text-[12px]">
              <tbody>
                {t.columns.map((c) => (
                  <tr key={c.name} className="border-t border-black/[0.05] align-top">
                    <td className="py-1.5 pr-3 font-mono text-[11.5px] font-semibold">{c.name}</td>
                    <td className="py-1.5 pr-3 text-[11px] text-ink-3">{c.type}</td>
                    <td className="py-1.5 text-ink-2">{c.description || <span className="text-ink-3">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <Card className="p-4" testId="wh-layer">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-[13.5px] font-semibold"><BookOpen size={15} /> The semantic layer</div>
            <div className="text-[12px] text-ink-2">What the model reads before every question: tables, columns, joins, metrics, examples and the bank's terms.</div>
          </div>
          <select data-testid="data-layer" value={layer} onChange={(e) => setLayer(e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1.5 font-mono text-[12px]">
            {st.layers.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <div className="mt-3 grid grid-cols-4 gap-2 text-center">
          {[[approved.length, "tables"], [L.metrics.length, "metrics"], [L.examples.length, "examples"], [L.terms.length, "terms"]].map(([n, s]) => (
            <div key={s as string} className="rounded-lg bg-mist px-2 py-2" data-testid={`layer-count-${s}`}><div className={`text-[20px] font-semibold ${s === "terms" && n === 0 ? "text-ember" : ""}`}>{n}</div><div className="text-[11px] text-ink-2">{s}</div></div>
          ))}
        </div>
        <div className="mt-2 flex items-center justify-between text-[11.5px] text-ink-3">
          <span>About {Math.round(L.prompt_chars / 4).toLocaleString()} tokens in every prompt.</span>
          {st.layer === layer ? <Chip tone="teal" >Used by Ask the data</Chip> : <Button variant="secondary" onClick={use} testId="use-layer">Use in Ask the data</Button>}
        </div>
        <div className="mt-3 flex gap-1">
          {(["terms", "yaml"] as const).map((v) => (
            <button key={v} onClick={() => setView(v)} data-testid={`layer-view-${v}`}
              className={`rounded-md px-2.5 py-1 text-[12px] font-semibold ${view === v ? "bg-navy text-white" : "bg-mist text-ink-2"}`}>{v === "terms" ? "The bank's terms" : `semantic/${layer}.yml`}</button>
          ))}
        </div>
        {view === "terms" ? (
          <div className="mt-2 space-y-2" data-testid="layer-terms">
            {L.terms.length === 0 && <div className="rounded-lg border border-dashed border-ember/40 bg-ember-50/50 px-3 py-3 text-[12.5px] text-ink-2">
              No terms yet. When someone asks about "turnaround" or "backlog", the model has to guess what the bank means.</div>}
            {L.terms.map((x) => (
              <div key={x.name} className="rounded-lg border border-black/[0.06] px-3 py-2">
                <div className="flex flex-wrap items-center gap-1.5"><span className="font-mono text-[12.5px] font-semibold">{x.name}</span>{(x.synonyms ?? []).map((s) => <Chip key={s}>{s}</Chip>)}</div>
                <div className="mt-1 text-[12px] text-ink-2">{x.means}</div>
                {x.sql && <div className="mt-1 font-mono text-[11px] text-ink-3">{x.sql}</div>}
              </div>
            ))}
          </div>
        ) : (
          <pre data-testid="layer-yaml" className="mt-2 max-h-[560px] overflow-auto rounded-lg bg-navy px-3 py-2 font-mono text-[11px] leading-relaxed text-white/90">{L.text}</pre>
        )}
      </Card>
    </div>
  );
}
