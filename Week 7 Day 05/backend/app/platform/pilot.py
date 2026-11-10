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
    raise NotImplementedError("Ticket ENG-502: check_pilot() is not built yet")


def routing_label(model_id: str) -> str:
    return {"in-region": "in-Region", "geo": "geographic", "global": "global"}[routing(model_id)]
