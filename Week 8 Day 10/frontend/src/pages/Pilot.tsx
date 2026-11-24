// Pilot: UC1 in the client's own AWS account in London, on Amazon Bedrock, deployed with Terraform (Day 5).
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import GuardrailsTab from "./pilot/GuardrailsTab";
import InfraTab from "./pilot/InfraTab";
import PlatformTab from "./pilot/PlatformTab";
import SpendTab from "./pilot/SpendTab";

const TABS = [
  { id: "platform", label: "Platform", hint: "Where does the model run?" },
  { id: "infrastructure", label: "Infrastructure", hint: "Does the plan meet the rules?" },
  { id: "guardrails", label: "Guardrails", hint: "Safe, and still accurate?" },
  { id: "spend", label: "Spend", hint: "What does it cost, and who stops it?" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "platform") as TabId;

export default function Pilot() {
  const [tab, setTab] = useState<TabId>(fromHash());
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/pilot/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">FDE control room <ChevronRight size={13} /> <span className="text-ink-2">Pilot</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Pilot: UC1 in the bank's AWS account, London</h1>
      <nav className="mt-4 grid grid-cols-4 gap-2">
        {TABS.map((t, i) => {
          const on = t.id === tab;
          return (
            <button key={t.id} data-testid={`ptab-${t.id}`} onClick={() => go(t.id)}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${on ? "border-navy bg-navy text-white" : "border-black/[0.06] bg-white hover:border-black/20"}`}>
              <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-[12px] font-bold ${on ? "bg-ember text-white" : "bg-mist text-ink-2"}`}>{i + 1}</span>
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold">{t.label}</span>
                <span className={`block truncate text-[11.5px] ${on ? "text-white/60" : "text-ink-3"}`}>{t.hint}</span>
              </span>
            </button>
          );
        })}
      </nav>
      <div className="mt-4">
        {tab === "platform" && <PlatformTab />}
        {tab === "infrastructure" && <InfraTab />}
        {tab === "guardrails" && <GuardrailsTab />}
        {tab === "spend" && <SpendTab />}
      </div>
    </div>
  );
}
