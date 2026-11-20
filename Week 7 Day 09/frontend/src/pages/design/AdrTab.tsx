import { CheckCircle2, FileText, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type Adr } from "../../api";
import { Card } from "../../components/ui";

export default function AdrTab() {
  const [adrs, setAdrs] = useState<Adr[] | null>(null);
  useEffect(() => { api.get<Adr[]>("/api/design/adrs").then(setAdrs); }, []);
  if (!adrs) return null;
  if (!adrs.length) return (
    <Card className="p-8 text-center" testId="no-adr">
      <FileText className="mx-auto text-ink-3" />
      <div className="mt-2 text-[14px] font-semibold">No decision record yet</div>
      <div className="mt-1 text-[12.5px] text-ink-2">Activity 3 writes docs/adr/ADR-001-extraction-architecture.md from data/Day02_Slide21_adr_template.md.</div>
    </Card>
  );
  return (
    <div className="space-y-4">
      {adrs.map((a) => {
        const ok = a.checks.filter((c) => c.ok).length;
        return (
          <div key={a.file} className="grid grid-cols-[1fr_320px] gap-4">
            <Card className="px-6 py-4" testId="adr">
              <div className="mb-2 font-mono text-[11.5px] text-ink-3">{a.file}</div>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
                h1: (p) => <h1 className="mb-2 text-[18px] font-semibold" {...p} />,
                h2: (p) => <h2 className="mb-1.5 mt-4 text-[14px] font-semibold text-teal" {...p} />,
                p: (p) => <p className="my-1.5 text-[12.5px] leading-relaxed text-ink-2" {...p} />,
                ul: (p) => <ul className="my-1.5 list-disc space-y-0.5 pl-5 text-[12.5px] text-ink-2" {...p} />,
                table: (p) => <table className="my-2 w-full text-left text-[12px]" {...p} />,
                th: (p) => <th className="border-b border-black/10 bg-mist px-2 py-1.5 font-semibold" {...p} />,
                td: (p) => <td className="border-b border-black/[0.05] px-2 py-1.5 align-top text-ink-2" {...p} />,
                strong: (p) => <strong className="font-semibold text-ink" {...p} />,
              }}>{a.markdown}</ReactMarkdown>
            </Card>
            <Card className="h-fit p-4" testId="adr-checks">
              <div className="text-[14px] font-semibold">Review checks</div>
              <div className={`text-[12px] ${ok === a.checks.length ? "text-teal" : "text-ember"}`}>{ok} of {a.checks.length} passed</div>
              <div className="mt-2 space-y-1.5">
                {a.checks.map((c) => (
                  <div key={c.check} className="flex items-start gap-2 text-[12.5px]">
                    {c.ok ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-teal" /> : <XCircle size={15} className="mt-0.5 shrink-0 text-ember" />}{c.check}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        );
      })}
    </div>
  );
}
