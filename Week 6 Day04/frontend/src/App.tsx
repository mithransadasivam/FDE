import { useEffect, useState } from "react";
import { api } from "./api";
import Sidebar from "./components/Sidebar";
import Cases from "./pages/Cases";
import Design from "./pages/Design";
import Discovery from "./pages/Discovery";
import Evaluation from "./pages/Evaluation";

// Screens are chosen by the address: #/discovery/..., #/design/..., #/cases/... or #/evaluation/...
const pageFromHash = () => (window.location.hash.split("/")[1] || "discovery");

export default function App() {
  const [fake, setFake] = useState<boolean | null>(null);
  const [page, setPage] = useState(pageFromHash());
  useEffect(() => {
    api.get<{ fake_llm: boolean }>("/api/health").then((h) => setFake(h.fake_llm)).catch(() => setFake(null));
    const on = () => setPage(pageFromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return (
    <div className="flex h-full min-h-[760px] text-ink">
      <Sidebar fake={fake} page={page} />
      <main className="min-w-0 flex-1 overflow-auto px-7 py-5">
        {page === "evaluation" ? <Evaluation /> : page === "cases" ? <Cases /> : page === "design" ? <Design /> : <Discovery />}
      </main>
    </div>
  );
}
