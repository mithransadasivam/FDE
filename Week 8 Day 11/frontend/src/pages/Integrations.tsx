// Integrations: the bank's systems behind the FDE's MCP server, used as the signed-in person (Day 8).
// Sign-in and tokens, acting as the person, webhooks into Slack, and the permission matrix for three roles.
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import ActTab from "./integration/ActTab";
import PermissionsTab from "./integration/PermissionsTab";
import SignInTab from "./integration/SignInTab";
import WebhooksTab from "./integration/WebhooksTab";

const TABS = [
  { id: "signin", label: "Sign-in", hint: "Whose token is this?" },
  { id: "act", label: "Act as the person", hint: "Who does the bank see?" },
  { id: "webhooks", label: "Webhooks → Slack", hint: "Who really sent it?" },
  { id: "permissions", label: "Permissions", hint: "Three roles, every tool" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const fromHash = (): TabId => (TABS.find((t) => t.id === window.location.hash.split("/")[2])?.id ?? "signin") as TabId;

export default function Integrations() {
  const [tab, setTab] = useState<TabId>(fromHash());
  useEffect(() => {
    const on = () => setTab(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (t: TabId) => { window.location.hash = `#/integrations/${t}`; setTab(t); };
  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="flex items-center gap-1.5 text-[12.5px] text-ink-3">FDE control room <ChevronRight size={13} /> <span className="text-ink-2">Integrations</span></div>
      <h1 className="mt-1 text-[24px] font-semibold tracking-tight">Integrations: the bank's systems, as the signed-in person</h1>
      <nav className="mt-4 grid grid-cols-4 gap-2">
        {TABS.map((t, i) => {
          const on = t.id === tab;
          return (
            <button key={t.id} data-testid={`dtab-${t.id}`} onClick={() => go(t.id)}
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
        {tab === "signin" && <SignInTab />}
        {tab === "act" && <ActTab />}
        {tab === "webhooks" && <WebhooksTab />}
        {tab === "permissions" && <PermissionsTab />}
      </div>
    </div>
  );
}
