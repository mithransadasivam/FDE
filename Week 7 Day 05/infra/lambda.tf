# The console's backend (FastAPI) and its built screens, as one Lambda function in the private subnet.

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/uc1-pilot"
  retention_in_days = 30
}

resource "aws_lambda_function" "pilot" {
  function_name    = "uc1-pilot"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  handler          = "lambda_entry.handler"
  filename         = var.lambda_zip
  source_code_hash = filebase64sha256(var.lambda_zip)
  timeout          = 300 # the first queue load reads 30 documents
  memory_size      = 1024

  vpc_config {
    subnet_ids         = [aws_subnet.private.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      FDE_LLM_PROVIDER      = "bedrock"
      FDE_BEDROCK_REGION    = var.region
      FDE_BEDROCK_MODEL_ID  = var.model_id
      FDE_GUARDRAIL_ID      = aws_bedrock_guardrail.uc1.guardrail_id
      FDE_GUARDRAIL_VERSION = aws_bedrock_guardrail_version.uc1.version
      FDE_PILOT_SECRET_ARN  = aws_secretsmanager_secret.pilot.arn
      FDE_STATIC_DIR        = "static"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.vpc_access,
    aws_iam_role_policy.bedrock,
    aws_iam_role_policy.secret,
  ]
}

# A public HTTPS address for the demo, protected by the analysts' password (checked by the app).
# A production bank would put it behind its own network or single sign-on (Day 8).
resource "aws_lambda_function_url" "pilot" {
  function_name      = aws_lambda_function.pilot.function_name
  authorization_type = "NONE"
}
