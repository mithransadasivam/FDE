// A document page with boxes drawn on it: every parsed word (Parse tab), or one field (Review queue).
import { useState } from "react";

export type Box = { box: number[]; tone: "teal" | "amber" | "ember" | "navy"; title?: string };
const TONE = { teal: "border-teal/70 bg-teal/10", amber: "border-amber bg-amber/15", ember: "border-ember bg-ember/15", navy: "border-navy bg-navy/10" };

export default function PageView({ src, boxes, testId, height = 640 }: { src: string; boxes: Box[]; testId?: string; height?: number }) {
  const [ready, setReady] = useState(false);
  return (
    <div data-testid={testId} className="relative mx-auto overflow-hidden rounded-lg border border-black/10 bg-mist" style={{ height, aspectRatio: "850 / 1100" }}>
      <img src={src} alt="" className="absolute inset-0 h-full w-full" onLoad={() => setReady(true)} />
      {ready && boxes.map((b, i) => (
        <div key={i} title={b.title} className={`absolute rounded-[2px] border ${TONE[b.tone]}`}
          style={{ left: `${b.box[0] * 100}%`, top: `${b.box[1] * 100}%`, width: `${(b.box[2] - b.box[0]) * 100}%`, height: `${(b.box[3] - b.box[1]) * 100}%` }} />
      ))}
    </div>
  );
}
