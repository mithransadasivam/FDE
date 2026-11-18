"""Day 5, ticket ENG-502: check the pilot's Terraform plan against the bank's rules, before anything is deployed.

On Day 2 you checked a drawing of each architecture (ENG-202). Today the same rules run on the real thing:
the plan Terraform will apply. Make it with:

    cd infra
    terraform plan -out pilot.tfplan
    terraform show -json pilot.tfplan > pilot.plan.json

The plan's "planned_values" lists every resource with the values Terraform already knows. Values only
known after apply (IDs, ARNs) are missing from it: the checks below use only values known at plan time.
"""

import json
from typing import Any

from pydantic import BaseModel

from app.platform.residency import UK_REGION, residency, routing

RULES = [
    ("residency", "Everything runs in London (eu-west-2)", "Helen"),
    ("model_in_region", "The model is called in-Region: customer data stays in the UK", "Helen"),
    ("no_internet", "No route to the internet, and the function runs inside the private network", "Helen"),
    ("private_model", "The model is reached through a private endpoint that allows only the pilot's calls", "Helen"),
    ("least_privilege", "The function may call only the model it needs: no wildcards", "Helen"),
    ("secrets", "No secret in plain text: the password lives in Secrets Manager", "Helen"),
    ("audit", "Every model call is logged, and every log group has a retention period", "Helen"),
    ("spend", "A monthly budget of at most USD 20, with an alert", "Martin"),
]
SECRET_WORDS = ("KEY", "SECRET", "TOKEN", "PASSWORD")
INTERNET = ("aws_internet_gateway", "aws_nat_gateway", "aws_egress_only_internet_gateway")


class PilotCheck(BaseModel):
    rule: str
    label: str
    owner: str
    ok: bool
    evidence: str  # one line: what in the plan passes or breaks the rule
    resources: list[str] = []  # the addresses of the resources it is about


def resources(plan: dict) -> list[dict]:
    """Every resource in the plan's planned_values, including those in child modules."""
    out, stack = [], [plan.get("planned_values", {}).get("root_module", {})]
    while stack:
        m = stack.pop()
        out += m.get("resources", [])
        stack += m.get("child_modules", [])
    return out


def of_type(plan: dict, rtype: str) -> list[dict]:
    return [r for r in resources(plan) if r.get("type") == rtype and r.get("mode", "managed") == "managed"]


def variable(plan: dict, name: str) -> Any:
    return plan.get("variables", {}).get(name, {}).get("value")


def lambda_env(r: dict) -> dict:
    env = r.get("values", {}).get("environment") or [{}]
    return (env[0] or {}).get("variables") or {}


def statements(policy: Any) -> list[dict]:
    """The statements of an IAM or endpoint policy given as a JSON string (as in the plan), or [] if unknown."""
    if not policy:
        return []
    doc = json.loads(policy) if isinstance(policy, str) else policy
    st = doc.get("Statement", [])
    return [st] if isinstance(st, dict) else st


def as_list(v: Any) -> list:
    return v if isinstance(v, list) else [v]


def plan_env(plan: dict, fn: dict) -> tuple[dict, bool]:
    """The function's environment as far as the plan knows it, and whether all of it is known.

    One value only known after apply (the guardrail ID) makes Terraform mark the whole variables map unknown.
    Then the plan's "configuration" still lists what the map refers to: var.region and var.model_id give us
    the region and the model, but not the names of the other keys.
    """
    env = lambda_env(fn)
    if env:
        return env, True
    cfg = next((r for r in plan.get("configuration", {}).get("root_module", {}).get("resources", [])
                if r.get("address") == fn.get("address")), {})
    envs = cfg.get("expressions", {}).get("environment") or [{}]
    refs = ((envs[0] or {}).get("variables") or {}).get("references") or []
    out = {}
    if "var.region" in refs:
        out["FDE_BEDROCK_REGION"] = variable(plan, "region")
    if "var.model_id" in refs:
        out["FDE_BEDROCK_MODEL_ID"] = variable(plan, "model_id")
    return out, False


def check_pilot(plan: dict) -> list[PilotCheck]:
    """Return one PilotCheck per rule in RULES, in that order.

    Each check is ok exactly when:
    - residency: the variable "region" is eu-west-2, and every aws_lambda_function's environment has
      FDE_BEDROCK_REGION = eu-west-2.
    - model_in_region: every function's FDE_BEDROCK_MODEL_ID (or, if a function has none, the variable "model_id")
      keeps data in the UK according to residency(model_id, region).
    - no_internet: there is no resource of a type in INTERNET, and every function has a non-empty vpc_config.
    - private_model: there is an aws_vpc_endpoint for "com.amazonaws.<region>.bedrock-runtime" of type Interface,
      with private_dns_enabled true and a policy in which no statement's Action is "*" or "bedrock:*".
      (An endpoint with no policy allows everything: that fails.)
    - least_privilege: at least one statement in the aws_iam_role_policy and aws_iam_policy resources allows
      "bedrock:InvokeModel"; and no Allow statement with a "bedrock:" action has Action "*" or "bedrock:*",
      or Resource "*". Policies whose value is unknown in the plan are skipped.
    - secrets: there is at least one aws_secretsmanager_secret, and no function has an environment variable
      whose name contains a word in SECRET_WORDS, unless the name ends with _ARN or _ID.
    - audit: there is an aws_bedrock_model_invocation_logging_configuration with text_data_delivery_enabled true
      and a cloudwatch_config or s3_config; and every aws_cloudwatch_log_group has retention_in_days above 0.
    - spend: there is an aws_budgets_budget with limit_unit USD, limit_amount at most 20, and at least one notification.

    Each check gives one line of evidence, and the addresses of the resources it looked at.
    """
    region = variable(plan, "region")
    fns = of_type(plan, "aws_lambda_function")
    labels = {r: (label, owner) for r, label, owner in RULES}
    out: dict[str, PilotCheck] = {}

    def add(rule: str, ok: bool, evidence: str, addrs: list[str]):
        label, owner = labels[rule]
        out[rule] = PilotCheck(rule=rule, label=label, owner=owner, ok=ok, evidence=evidence, resources=addrs)

    def addr(rs: list[dict]) -> list[str]:
        return [r.get("address", "") for r in rs]

    # 1 residency
    bad = [f for f in fns if plan_env(plan, f)[0].get("FDE_BEDROCK_REGION") != UK_REGION]
    ok = region == UK_REGION and not bad
    if region != UK_REGION:
        ev = f"variable region is {region!r}, not {UK_REGION}"
    elif bad:
        ev = f"{bad[0].get('address')} calls Bedrock in {plan_env(plan, bad[0])[0].get('FDE_BEDROCK_REGION')!r}, not {UK_REGION}"
    else:
        ev = f"region = {region}; functions call Bedrock in {UK_REGION}"
    add("residency", ok, ev, addr(fns))

    # 2 model_in_region
    ok, ev = bool(fns), "no function in the plan"
    for f in fns:
        mid = plan_env(plan, f)[0].get("FDE_BEDROCK_MODEL_ID") or variable(plan, "model_id")
        v = residency(mid, region or UK_REGION)
        ev = f"{mid} is {routing_label(mid)}: processed in {v['processed_in']}"
        if not v["stays_in_uk"]:
            ok = False
            break
    add("model_in_region", ok, ev, addr(fns))

    # 3 no_internet
    gateways = [r for t in INTERNET for r in of_type(plan, t)]
    outside = [f for f in fns if not f.get("values", {}).get("vpc_config")]
    if gateways:
        ev = f"{gateways[0].get('address')} gives a route to the internet"
    elif outside:
        ev = f"{outside[0].get('address')} runs outside the VPC"
    else:
        ev = "no internet or NAT gateway; every function runs in the VPC"
    add("no_internet", not gateways and not outside and bool(fns), ev, addr(gateways + outside) or addr(fns))

    # 4 private_model
    svc = f"com.amazonaws.{region}.bedrock-runtime"
    eps = [e for e in of_type(plan, "aws_vpc_endpoint") if e["values"].get("service_name") == svc]
    ok, ev = False, f"no Interface endpoint for {svc}"
    for e in eps:
        v = e["values"]
        sts = statements(v.get("policy"))
        if v.get("vpc_endpoint_type") != "Interface":
            ev = f"{e['address']} is not an Interface endpoint"
        elif not v.get("private_dns_enabled"):
            ev = f"{e['address']} has private DNS off"
        elif not sts:
            ev = f"{e['address']} has no policy: it allows everything"
        elif any(x in ("*", "bedrock:*") for st in sts for x in as_list(st.get("Action", []))):
            ev = f"{e['address']} policy allows a wildcard action"
        else:
            ok = True
            acts = sorted({a for st in sts for a in as_list(st.get("Action", []))})
            ev = f"Interface endpoint with private DNS; its policy allows only {', '.join(acts)}"
            break
    add("private_model", ok, ev, addr(eps))

    # 5 least_privilege
    pols = of_type(plan, "aws_iam_role_policy") + of_type(plan, "aws_iam_policy")
    invoke, problem, seen = False, "", []
    for r in pols:
        sts = statements(r.get("values", {}).get("policy"))
        if sts:
            seen.append(r["address"])
        for st in sts:
            if st.get("Effect") != "Allow":
                continue
            acts = [a for a in as_list(st.get("Action", [])) if str(a).startswith("bedrock:")]
            if not acts:
                continue
            if "bedrock:InvokeModel" in acts:
                invoke = True
            if "bedrock:*" in acts or "*" in as_list(st.get("Action", [])) or "*" in as_list(st.get("Resource", [])):
                problem = problem or f"{r['address']} allows {', '.join(acts)} on {', '.join(map(str, as_list(st.get('Resource', []))))}"
    if problem:
        ok, ev = False, problem
    elif not invoke:
        ok, ev = False, "no policy allows bedrock:InvokeModel"
    else:
        ok, ev = True, "bedrock:InvokeModel is allowed on named resources only, no wildcards"
    add("least_privilege", ok, ev, seen)

    # 6 secrets
    secrets = of_type(plan, "aws_secretsmanager_secret")
    leaks = [(f["address"], k) for f in fns for k in plan_env(plan, f)[0]
             if any(w in k.upper() for w in SECRET_WORDS) and not k.upper().endswith(("_ARN", "_ID"))]
    if leaks:
        ok, ev = False, f"{leaks[0][0]} has {leaks[0][1]} in plain text"
    elif not secrets:
        ok, ev = False, "no Secrets Manager secret in the plan"
    else:
        partial = any(not plan_env(plan, f)[1] for f in fns)
        note = " (some environment values are only known after apply, so key names could not all be read)" if partial else ""
        ok, ev = True, f"{len(secrets)} secret(s) in Secrets Manager; no secret in any function's environment{note}"
    add("secrets", ok, ev, addr(secrets) + [a for a, _ in leaks])

    # 7 audit
    logcfg = of_type(plan, "aws_bedrock_model_invocation_logging_configuration")
    logging_ok = any(
        c.get("text_data_delivery_enabled") and (c.get("cloudwatch_config") or c.get("s3_config"))
        for r in logcfg for c in (r["values"].get("logging_config") or [])
    )
    groups = of_type(plan, "aws_cloudwatch_log_group")
    no_ret = [g for g in groups if not (g["values"].get("retention_in_days") or 0) > 0]
    if not logging_ok:
        ok, ev = False, "model invocation logging is missing, or text delivery is off"
    elif no_ret:
        ok, ev = False, f"{no_ret[0]['address']} has no retention period"
    else:
        days = sorted({g["values"]["retention_in_days"] for g in groups})
        ok, ev = True, f"every model call is logged; {len(groups)} log groups kept {', '.join(map(str, days))} days"
    add("audit", ok, ev, addr(logcfg) + addr(groups))

    # 8 spend
    budgets = of_type(plan, "aws_budgets_budget")
    ok, ev = False, "no budget in the plan"
    for b in budgets:
        v = b["values"]
        amt = float(v.get("limit_amount") or 0)
        if v.get("limit_unit") != "USD":
            ev = f"{b['address']} is in {v.get('limit_unit')}, not USD"
        elif amt > 20:
            ev = f"{b['address']} allows USD {v.get('limit_amount')} a month, more than USD 20"
        elif not v.get("notification"):
            ev = f"{b['address']} has no alert"
        else:
            ok, ev = True, f"USD {v['limit_amount']} a month, {len(v['notification'])} alerts"
            break
    add("spend", ok, ev, addr(budgets))

    return [out[r] for r, _, _ in RULES]


def routing_label(model_id: str) -> str:
    return {"in-region": "in-Region", "geo": "geographic", "global": "global"}[routing(model_id)]
