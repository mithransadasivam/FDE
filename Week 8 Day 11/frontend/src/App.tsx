import { useEffect, useState } from "react";
import { api } from "./api";
import Sidebar from "./components/Sidebar";
import AgentRuns from "./pages/AgentRuns";
import Workflows from "./pages/Workflows";
import ModelLab from "./pages/ModelLab";
import AskData from "./pages/AskData";
import Cases from "./pages/Cases";
import DataAgent from "./pages/DataAgent";
import Design from "./pages/Design";
import Discovery from "./pages/Discovery";
import Evaluation from "./pages/Evaluation";
import Integrations from "./pages/Integrations";
import Pilot from "./pages/Pilot";
import Pipeline from "./pages/Pipeline";
import ReviewQueue from "./pages/ReviewQueue";

// Screens are chosen by the address: #/discovery/..., #/design/..., #/cases/..., #/evaluation/..., #/pilot/..., #/pipeline/..., #/queue, #/ask, #/data/..., #/integrations/..., #/agent/... or #/workflows/...
const pageFromHash = () => (window.location.hash.split("/")[1] || "discovery");

export default function App() {
  const [fake, setFake] = useState<boolean | null>(null);
  const [model, setModel] = useState("");
  const [page, setPage] = useState(pageFromHash());
  useEffect(() => {
    api.get<{ fake_llm: boolean; model?: string }>("/api/health").then((h) => { setFake(h.fake_llm); setModel(h.model ?? ""); }).catch(() => setFake(null));
    const on = () => setPage(pageFromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return (
    <div className="flex h-full min-h-[760px] text-ink">
      <Sidebar fake={fake} page={page} model={model} />
      <main className="min-w-0 flex-1 overflow-auto px-7 py-5">
        {page === "modellab" ? <ModelLab /> : page === "workflows" ? <Workflows /> : page === "agent" ? <AgentRuns /> : page === "integrations" ? <Integrations /> : page === "ask" ? <AskData /> : page === "data" ? <DataAgent /> : page === "pipeline" ? <Pipeline /> : page === "queue" ? <ReviewQueue /> : page === "pilot" ? <Pilot /> : page === "evaluation" ? <Evaluation /> : page === "cases" ? <Cases /> : page === "design" ? <Design /> : <Discovery />}
      </main>
    </div>
  );
}
