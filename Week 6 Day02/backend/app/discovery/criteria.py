"""Activity 4 (ticket ENG-102): is a success criterion measurable?

A criterion the client cannot measure cannot be met. check_criterion() returns what is missing,
in a fixed order, so the console can show it next to the criterion.
"""

from app.discovery.models import Criterion

PROBLEMS = {
    "vague": "metric is vague: say exactly what you count or time (at least 4 words)",
    "no_target": "no target",
    "no_baseline": "no baseline: a business criterion needs a before and an after",
    "no_unit": "no unit",
    "wrong_way": "target does not improve on the baseline",
    "no_method": "no measurement method: say where the number comes from",
    "no_owner": "no owner",
    "no_deadline": "no deadline",
}


def check_criterion(c: Criterion) -> list[str]:
    """Return the problems with criterion c, as texts from PROBLEMS, in this order:
    vague, no_target, no_baseline, no_unit, wrong_way, no_method, no_owner, no_deadline.

    - vague: the metric has fewer than 4 words
    - no_target: target is None
    - no_baseline: only for kind "business", when baseline is None
    - no_unit: unit is blank
    - wrong_way: baseline and target are both set, and the target is not better in the
      criterion's direction (for "decrease" it must be lower, for "increase" higher)
    - no_method: measured_how has fewer than 10 characters (ignoring spaces at the ends)
    - no_owner / no_deadline: owner / by_when is blank
    An empty list means the criterion is measurable.
    """
    found = []
    if len(c.metric.split()) < 4:
        found.append("vague")
    if c.target is None:
        found.append("no_target")
    if c.kind == "business" and c.baseline is None:
        found.append("no_baseline")
    if not c.unit.strip():
        found.append("no_unit")
    if c.baseline is not None and c.target is not None:
        better = c.target < c.baseline if c.direction == "decrease" else c.target > c.baseline
        if not better:
            found.append("wrong_way")
    if len(c.measured_how.strip()) < 10:
        found.append("no_method")
    if not c.owner.strip():
        found.append("no_owner")
    if not c.by_when.strip():
        found.append("no_deadline")
    return [PROBLEMS[key] for key in found]
