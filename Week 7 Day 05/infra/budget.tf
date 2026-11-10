# Martin's spending limit. A budget alone only sends emails; the budget action is the quota:
# at 100% of actual spend it attaches a policy that denies the pilot's role any Bedrock call.
# Billing data reaches AWS Budgets a few times a day, so this is a backstop, not a real-time cap.

resource "aws_budgets_budget" "pilot" {
  name         = "uc1-pilot-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

resource "aws_iam_policy" "deny_bedrock" {
  name        = "uc1-pilot-deny-bedrock"
  description = "Attached by the budget action when the pilot budget is spent"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Deny"
      Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:ApplyGuardrail"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role" "budget_action" {
  name = "uc1-pilot-budget-action"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "budgets.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "budget_action" {
  name = "uc1-pilot-apply-deny"
  role = aws_iam_role.budget_action.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
      Resource = [aws_iam_role.lambda.arn]
      Condition = {
        ArnEquals = { "iam:PolicyARN" = aws_iam_policy.deny_bedrock.arn }
      }
    }]
  })
}

resource "aws_budgets_budget_action" "stop_bedrock" {
  budget_name        = aws_budgets_budget.pilot.name
  action_type        = "APPLY_IAM_POLICY"
  approval_model     = "AUTOMATIC"
  notification_type  = "ACTUAL"
  execution_role_arn = aws_iam_role.budget_action.arn

  action_threshold {
    action_threshold_type  = "PERCENTAGE"
    action_threshold_value = 100
  }

  definition {
    iam_action_definition {
      policy_arn = aws_iam_policy.deny_bedrock.arn
      roles      = [aws_iam_role.lambda.name]
    }
  }

  subscriber {
    address           = var.alert_email
    subscription_type = "EMAIL"
  }
}
