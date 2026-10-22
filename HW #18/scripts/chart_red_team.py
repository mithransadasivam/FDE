"""Chart which attacks worked: python -m scripts.chart_red_team before  (reads logs/red_team_<label>.json)."""
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

label = sys.argv[1] if len(sys.argv) > 1 else "before"
data = json.load(open(f"logs/red_team_{label}.json", encoding="utf-8"))
rows = data["results"]

INK, MUTED, GRID, SURFACE = "#1f2430", "#6b7280", "#e5e7eb", "#ffffff"
WORKED, STOPPED = "#c0392b", "#2a9d8f"
DAMAGE = {"A01", "A02", "A03", "A05"}  # changed or deleted data

fig, ax = plt.subplots(figsize=(13, 7.2), facecolor=SURFACE)
ax.set_facecolor(SURFACE)
y = 0
ticks, names = [], []
for target in ("chatbot", "agent"):
    group = [r for r in rows if r["target"] == target]
    for r in group:
        ok = r["succeeded"]
        ax.barh(y, 1, height=0.55, color=WORKED if ok else STOPPED, edgecolor=SURFACE, linewidth=2)
        ax.text(0.02, y, "WORKED" if ok else "STOPPED", va="center", ha="left", color="white", fontsize=9, fontweight="bold")
        ev = r.get("evidence") or ", ".join(r.get("guardrail", [])) or "blocked"
        if r["id"] in DAMAGE:
            ev += "   [changed data]"
        ax.text(1.02, y, ev, va="center", ha="left", color=INK, fontsize=9)
        ticks.append(y)
        names.append(f'{r["id"]}  {r["technique"]}')
        y += 1
    y += 0.6
ax.set_yticks(ticks)
ax.set_yticklabels(names, fontsize=9, color=INK)
ax.invert_yaxis()
ax.set_xlim(0, 2.3)
ax.set_xticks([])
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)
worked = sum(r["succeeded"] for r in rows)
ax.set_title(f"{worked} of {len(rows)} attacks worked ({label})", loc="left", x=-0.9, fontsize=15, fontweight="bold", color=INK, pad=28)
by = {t: (sum(r["succeeded"] for r in rows if r["target"] == t), sum(r["target"] == t for r in rows)) for t in ("chatbot", "agent")}
ax.text(-0.9, -1.1, f'Chatbot {by["chatbot"][0]}/{by["chatbot"][1]}  ·  Agent {by["agent"][0]}/{by["agent"][1]}  ·  fake model, no guardrails',
        color=MUTED, fontsize=10, transform=ax.transData)
plt.tight_layout()
out = f"logs/red_team_{label}.png"
fig.savefig(out, dpi=150)
print("saved", out)
