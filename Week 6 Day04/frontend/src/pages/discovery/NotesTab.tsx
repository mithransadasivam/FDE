import { Check, Ear } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type Question } from "../../api";
import { Card } from "../../components/ui";

const LISTEN_FOR = [
  "Numbers: volumes, minutes, percentages, money",
  "The last real example, step by step",
  "What has been tried before, and why it stopped",
  "What data and history exist",
  "Who must approve, and how long that takes",
  "Where data may and may not go",
  "How the sponsor will judge success",
  "Peaks, deadlines and dates",
];

export default function NotesTab({ onChange }: { onChange: () => void }) {
  const [text, setText] = useState("");
  const [saved, setSaved] = useState<"idle" | "saving" | "saved">("idle");
  const [starred, setStarred] = useState<Question[]>([]);
  const [asked, setAsked] = useState<Record<string, boolean>>({});
  const timer = useRef<number>();
  const typed = useRef(false); // never overwrite what the user has already typed

  useEffect(() => {
    api.get<{ text: string }>("/api/notes").then((n) => { if (!typed.current) setText(n.text); });
    api.get<Question[]>("/api/questions").then((qs) => setStarred(qs.filter((q) => q.starred)));
  }, []);
  const edit = (v: string) => {
    typed.current = true; setText(v); setSaved("saving");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => { await api.put("/api/notes", { text: v }); setSaved("saved"); onChange(); }, 600);
  };
  const words = text.split(/\s+/).filter(Boolean).length;

  return (
    <div className="grid grid-cols-[1fr_340px] gap-4">
      <Card className="flex flex-col p-4">
        <div className="flex items-center justify-between">
          <div className="text-[14px] font-semibold">Interview notes</div>
          <div className="text-[12px] text-ink-3" data-testid="notes-status">{words} words · {saved === "saving" ? "saving…" : saved === "saved" ? "saved to engagement/interview_notes.md" : "autosaves as you type"}</div>
        </div>
        <textarea data-testid="notes" value={text} onChange={(e) => edit(e.target.value)}
          placeholder={"Write what you hear, with numbers and who said it.\n\nDeborah: median 7 working days, promise is 3 …"}
          className="mt-3 min-h-[460px] flex-1 resize-none rounded-lg border border-black/[0.08] bg-mist/60 p-4 font-mono text-[13px] leading-relaxed outline-none focus:border-teal focus:bg-white" />
      </Card>
      <div className="space-y-3">
        <Card className="p-4">
          <div className="flex items-center gap-2 text-[13px] font-semibold"><Ear size={15} className="text-teal" /> Listen for</div>
          <ul className="mt-2 space-y-1.5 text-[12.5px] text-ink-2">
            {LISTEN_FOR.map((l) => <li key={l} className="flex gap-2"><span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-teal" />{l}</li>)}
          </ul>
        </Card>
        <Card className="p-4">
          <div className="text-[13px] font-semibold">Your starred questions</div>
          <div className="mt-2 space-y-1.5">
            {starred.map((q) => (
              <button key={q.id} onClick={() => setAsked((a) => ({ ...a, [q.id]: !a[q.id] }))}
                className={`flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left text-[12px] ${asked[q.id] ? "bg-teal-50 text-ink-3 line-through" : "hover:bg-mist"}`}>
                <span className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border ${asked[q.id] ? "border-teal bg-teal text-white" : "border-black/20"}`}>{asked[q.id] && <Check size={11} />}</span>
                {q.text}
              </button>
            ))}
            {!starred.length && <div className="text-[12px] text-ink-3">Star questions in the question plan first.</div>}
          </div>
        </Card>
      </div>
    </div>
  );
}
