"""Ticket ENG-502: the bank's rules, checked on the pilot's Terraform plan."""

import copy
import json
from pathlib import Path

import pytest

from app.platform.pilot import RULES, check_pilot, of_type

FIX = Path(__file__).parent / "fixtures" / "pilot"
GOOD = json.loads((FIX / "plan_good.json").read_text())


def by_rule(plan):
    return {c.rule: c for c in check_pilot(plan)}


def edit(fn):
    p = copy.deepcopy(GOOD)
    fn(p)
    return p


def resource(p, rtype, name):
    return next(r for r in p["planned_values"]["root_module"]["resources"] if r["type"] == rtype and r["name"] == name)


def test_good_plan_meets_every_rule_in_order():
    checks = check_pilot(GOOD)
    assert [c.rule for c in checks] == [r for r, _, _ in RULES]
    assert all(c.ok for c in checks), [c.evidence for c in checks if not c.ok]
    assert all(c.evidence for c in checks)


def test_start_plan_fails_only_the_model_rule():
    checks = by_rule(json.loads((FIX / "plan_start.json").read_text()))
    assert [r for r, c in checks.items() if not c.ok] == ["model_in_region"]
    assert "eu.anthropic.claude-haiku-5-5" in checks["model_in_region"].evidence


def test_wrong_region_fails_residency():
    p = edit(lambda p: p["variables"]["region"].update(value="eu-west-1"))
    assert not by_rule(p)["residency"].ok


def test_global_profile_fails_model_in_region():
    def f(p):
        resource(p, "aws_lambda_function", "pilot")["values"]["environment"][0]["variables"]["FDE_BEDROCK_MODEL_ID"] = "global.anthropic.claude-sonnet-5"
    c = by_rule(edit(f))["model_in_region"]
    assert not c.ok and "global" in c.evidence


def test_nat_gateway_fails_no_internet():
    def f(p):
        p["planned_values"]["root_module"]["resources"].append({"address": "aws_nat_gateway.out", "mode": "managed", "type": "aws_nat_gateway",
                                                                "name": "out", "values": {"connectivity_type": "public"}})
    c = by_rule(edit(f))["no_internet"]
    assert not c.ok and "aws_nat_gateway.out" in c.resources


def test_function_outside_the_vpc_fails_no_internet():
    p = edit(lambda p: resource(p, "aws_lambda_function", "pilot")["values"].update(vpc_config=[]))
    assert not by_rule(p)["no_internet"].ok


@pytest.mark.parametrize("change", [
    lambda v: v.update(policy=None),
    lambda v: v.update(policy=json.dumps({"Statement": [{"Effect": "Allow", "Principal": "*", "Action": "bedrock:*", "Resource": "*"}]})),
    lambda v: v.update(private_dns_enabled=False),
])
def test_endpoint_problems_fail_private_model(change):
    p = edit(lambda p: change(resource(p, "aws_vpc_endpoint", "bedrock_runtime")["values"]))
    assert not by_rule(p)["private_model"].ok


def test_missing_endpoint_fails_private_model():
    p = edit(lambda p: p["planned_values"]["root_module"].update(
        resources=[r for r in p["planned_values"]["root_module"]["resources"] if r["address"] != "aws_vpc_endpoint.bedrock_runtime"]))
    assert not by_rule(p)["private_model"].ok


def test_wildcard_resource_fails_least_privilege():
    def f(p):
        v = resource(p, "aws_iam_role_policy", "bedrock")["values"]
        doc = json.loads(v["policy"])
        doc["Statement"][0]["Resource"] = "*"
        v["policy"] = json.dumps(doc)
    c = by_rule(edit(f))["least_privilege"]
    assert not c.ok and "aws_iam_role_policy.bedrock" in c.resources


def test_deny_statements_are_not_privileges():
    assert of_type(GOOD, "aws_iam_policy") and by_rule(GOOD)["least_privilege"].ok  # the budget's deny policy uses Resource "*"


def test_plain_text_key_fails_secrets():
    def f(p):
        resource(p, "aws_lambda_function", "pilot")["values"]["environment"][0]["variables"]["OPENROUTER_API_KEY"] = "sk-or-v1-abc"
    c = by_rule(edit(f))["secrets"]
    assert not c.ok and "OPENROUTER_API_KEY" in c.evidence


def test_arn_variable_is_not_a_secret():
    def f(p):
        resource(p, "aws_lambda_function", "pilot")["values"]["environment"][0]["variables"]["FDE_PILOT_SECRET_ARN"] = "arn:aws:secretsmanager:eu-west-2:1:secret:x"
    assert by_rule(edit(f))["secrets"].ok


def test_log_group_without_retention_fails_audit():
    p = edit(lambda p: resource(p, "aws_cloudwatch_log_group", "lambda")["values"].update(retention_in_days=0))
    assert not by_rule(p)["audit"].ok


def test_logging_off_fails_audit():
    p = edit(lambda p: resource(p, "aws_bedrock_model_invocation_logging_configuration", "pilot")["values"]["logging_config"][0]
             .update(text_data_delivery_enabled=False))
    assert not by_rule(p)["audit"].ok


def test_budget_over_20_fails_spend():
    p = edit(lambda p: resource(p, "aws_budgets_budget", "pilot")["values"].update(limit_amount="200"))
    c = by_rule(p)["spend"]
    assert not c.ok and "200" in c.evidence
