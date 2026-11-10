// How each field status looks: shared by the field boxes on the page and the field list beside it.
import type { CaseField, FieldStatus } from "../api";

export const STATUS_STYLE: Record<FieldStatus, { border: string; chip: string; text: string }> = {
  ok: { border: "border-teal", chip: "bg-teal", text: "sure" },
  check: { border: "border-amber", chip: "bg-amber", text: "check" },
  doubtful: { border: "border-ember", chip: "bg-ember", text: "doubtful" },
  not_on_page: { border: "border-ember border-dashed", chip: "bg-ember", text: "not on the page" },
  missing: { border: "border-ember border-dashed", chip: "bg-ember", text: "missing" },
  confirmed: { border: "border-navy", chip: "bg-navy", text: "confirmed" },
};

export const chipText = (f: CaseField) =>
  f.status === "ok" || f.status === "check" || f.status === "doubtful" ? `${f.label} · ${f.confidence.toFixed(2)}` : `${f.label} · ${STATUS_STYLE[f.status].text}`;
