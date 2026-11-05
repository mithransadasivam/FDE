"""Day 2, Activity 3: print the numbers the decision record needs (run from backend/).

    python -m scripts.design_numbers
"""

from app.design.architecture import check_architecture, load_options
from app.design.cost import estimate, load_prices, value_per_month

p = load_prices()
print("Run-cost per month (GBP), 1.4 pages per document")
print(f"{'Option':<32}{'8,600 docs (today)':>20}{'17,200 docs (peak)':>20}")
for a in load_options():
    today, peak = estimate(a.cost, 8600, 1.4, p)["total_gbp"], estimate(a.cost, 17200, 1.4, p)["total_gbp"]
    print(f"{a.id + ' · ' + a.name:<32}{'£' + format(today, ',.0f'):>20}{'£' + format(peak, ',.0f'):>20}")
print(f"\nValue of analyst time saved at 3 minutes a document: £{value_per_month(8600, 3, p):,.0f} a month today")
print("\nClient rules")
for a in load_options():
    try:
        vs = check_architecture(a)
        print(f"Option {a.id}: " + ("meets all 5 rules" if not vs else f"{len(vs)} broken: " + "; ".join(v.message for v in vs)))
    except NotImplementedError:
        print(f"Option {a.id}: not checked (ticket ENG-202 not built yet)")
    print(f"   time to pilot: {a.time_to_pilot_weeks:g} week{'' if a.time_to_pilot_weeks == 1 else 's'} · strengths: {'; '.join(a.strengths)} · weaknesses: {'; '.join(a.weaknesses)}")
