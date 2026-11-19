// Which document set the Pipeline and the Review queue show. Remembered in this browser only.
import { useState } from "react";

const KEY = "fde.pipeline.set";

export function useDocSet(): [string, (s: string) => void] {
  const [set, setSet] = useState<string>(() => {
    try { return localStorage.getItem(KEY) || "october"; } catch { return "october"; }
  });
  const choose = (s: string) => {
    try { localStorage.setItem(KEY, s); } catch { /* private window: not remembered */ }
    setSet(s);
  };
  return [set, choose];
}
