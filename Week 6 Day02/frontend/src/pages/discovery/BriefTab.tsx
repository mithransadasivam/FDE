import { Building2, CalendarClock, Crown, Gauge, Timer, UserRound, Users, Workflow } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../../api";
import { Card } from "../../components/ui";

const ICONS = [Building2, Users, Crown, UserRound, Workflow, Gauge, Timer, CalendarClock];

export default function BriefTab() {
  const [brief, setBrief] = useState<{ markdown: string; facts: { label: string; value: string }[] } | null>(null);
  useEffect(() => { api.get<typeof brief>("/api/brief").then(setBrief); }, []);
  if (!brief) return null;
  const body = brief.markdown.split("## The request")[1] ?? "";
  return (
    <div className="grid grid-cols-[400px_1fr] gap-4">
      <div className="grid grid-cols-2 content-start gap-2.5">
        {brief.facts.map((f, i) => {
          const I = ICONS[i % ICONS.length];
          return (
            <Card key={f.label} className="p-3">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-3"><I size={13} /> {f.label}</div>
              <div className="mt-1 text-[13px] font-medium leading-snug">{f.value}</div>
            </Card>
          );
        })}
      </div>
      <Card className="px-6 py-4" testId="brief">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h2: (p) => <h2 className="mb-2 mt-4 text-[15px] font-semibold first:mt-0" {...p} />,
            p: (p) => <p className="my-2 text-[13px] leading-relaxed text-ink-2" {...p} />,
            ul: (p) => <ul className="my-2 list-disc space-y-1 pl-5 text-[13px] text-ink-2" {...p} />,
            blockquote: (p) => <blockquote className="my-3 rounded-r-lg border-l-4 border-teal bg-teal-50 px-4 py-1 text-[13px]" {...p} />,
            table: (p) => <table className="my-3 w-full text-left text-[12.5px]" {...p} />,
            th: (p) => <th className="border-b border-black/10 py-1.5 pr-3 font-semibold" {...p} />,
            td: (p) => <td className="border-b border-black/[0.05] py-1.5 pr-3 align-top text-ink-2" {...p} />,
            strong: (p) => <strong className="font-semibold text-ink" {...p} />,
          }}>
          {"## The request" + body}
        </ReactMarkdown>
      </Card>
    </div>
  );
}
