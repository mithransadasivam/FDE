// Ticket ENG-303: a box on the page for every field, coloured by how sure it is.
// The parent places this over the page image in a `relative` container of exactly the image's size,
// so a field's box [x0, y0, x1, y1] (0–1 of the page) maps straight to percentages.
import type { CaseField } from "../api";
import { chipText, STATUS_STYLE } from "./fieldStyle";

const pct = (n: number) => `${n * 100}%`;

function FieldBox({ field, selected, onSelect }: { field: CaseField; selected: boolean; onSelect: (name: string) => void }) {
  const [x0, y0, x1, y1] = field.box!;
  const look = STATUS_STYLE[field.status];
  // the address sits right under the name, so its chip goes below the box
  const chipSide = field.name === "address" ? "top-full mt-0.5" : "bottom-full mb-0.5";
  return (
    <button
      type="button"
      data-testid={`box-${field.name}`}
      data-status={field.status}
      data-selected={selected ? "true" : "false"}
      onClick={() => onSelect(field.name)}
      style={{ left: pct(x0), top: pct(y0), width: pct(x1 - x0), height: pct(y1 - y0) }}
      className={`absolute border-2 ${look.border} ${selected ? "z-10 ring-2 ring-navy/60 ring-offset-1" : ""}`}
    >
      <span className={`pointer-events-none absolute left-0 ${chipSide} whitespace-nowrap rounded px-1.5 py-px text-[10.5px] font-semibold leading-tight text-white ${look.chip}`}>
        {chipText(field)}
      </span>
    </button>
  );
}

export default function FieldBoxes({ fields, selected, onSelect }: {
  fields: CaseField[]; selected: string | null; onSelect: (name: string) => void;
}) {
  return (
    <>
      {fields.filter((f) => f.box).map((f) => (
        <FieldBox key={f.name} field={f} selected={selected === f.name} onSelect={onSelect} />
      ))}
    </>
  );
}
