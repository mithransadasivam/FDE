# The pilot function's role: it may call one model, apply this account's guardrails,
# and read one secret. No long-lived keys anywhere: the function gets short-lived credentials from the role.

resource "aws_iam_role" "lambda" {
  name = "uc1-pilot-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Lets the function create its network interfaces in the private subnet, and write its own logs.
resource "aws_iam_role_policy_attachment" "vpc_access" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "bedrock" {
  name = "uc1-pilot-bedrock"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "InvokeThePilotModel"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = [local.model_arn]
      },
      {
        Sid      = "ApplyTheGuardrail"
        Effect   = "Allow"
        Action   = ["bedrock:ApplyGuardrail"]
        Resource = [local.guardrail_arns]
      }
    ]
  })
}

resource "aws_iam_role_policy" "secret" {
  name = "uc1-pilot-secret"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadTheAnalystPassword"
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.pilot.arn]
    }]
  })
}
