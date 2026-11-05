// Ticket ENG-303: draw a box on the document for every field, coloured by how sure it is.
// The parent (pages/cases/CaseReview.tsx) places this over the page image in a `relative` container
// of exactly the image's size, so a field's box [x0, y0, x1, y1] (0–1 of the page) maps to percentages.
// Read docs/tickets/ENG-303.md. Use STATUS_STYLE and chipText() from ./fieldStyle.
import type { CaseField } from "../api";
import { chipText, STATUS_STYLE } from "./fieldStyle";

export default function FieldBoxes({ fields, selected, onSelect }: {
  fields: CaseField[]; selected: string | null; onSelect: (name: string) => void;
}) {
  return (
    <>
      {fields.filter((f) => f.box).map((f) => {
        const [x0, y0, x1, y1] = f.box!;
        const style = STATUS_STYLE[f.status];
        const on = selected === f.name;
        // the address sits right under the name, so its chip goes below to keep both readable
        const chipPos = f.name === "address" ? "top-full mt-0.5" : "bottom-full mb-0.5";
        return (
          <button key={f.name} type="button" data-testid={`box-${f.name}`} data-status={f.status} data-selected={on}
            onClick={() => onSelect(f.name)}
            style={{ left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` }}
            className={`absolute border-2 ${style.border} ${on ? "z-10 ring-2 ring-navy/60 ring-offset-1" : ""}`}>
            <span className={`pointer-events-none absolute left-0 ${chipPos} whitespace-nowrap rounded px-1.5 py-px text-[10.5px] font-semibold leading-tight text-white ${style.chip}`}>
              {chipText(f)}
            </span>
          </button>
        );
      })}
    </>
  );
}
