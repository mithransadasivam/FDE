# Helen's audit rule: every model call is logged. Bedrock writes each request and reply to CloudWatch Logs
# in London. The logs hold customer data, so they are kept 30 days and only this account can read them.
# Note: this setting applies to the whole account in this Region, not only to the pilot.

resource "aws_cloudwatch_log_group" "invocations" {
  name              = "/aws/bedrock/uc1-pilot-invocations"
  retention_in_days = 30
}

resource "aws_iam_role" "bedrock_logging" {
  name = "uc1-pilot-bedrock-logging"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_logging" {
  name = "uc1-pilot-write-invocation-logs"
  role = aws_iam_role.bedrock_logging.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = ["${aws_cloudwatch_log_group.invocations.arn}:*"]
    }]
  })
}

resource "aws_bedrock_model_invocation_logging_configuration" "pilot" {
  logging_config {
    text_data_delivery_enabled      = true
    image_data_delivery_enabled     = false
    embedding_data_delivery_enabled = false
    video_data_delivery_enabled     = false
    cloudwatch_config {
      log_group_name = aws_cloudwatch_log_group.invocations.name
      role_arn       = aws_iam_role.bedrock_logging.arn
    }
  }
  depends_on = [aws_iam_role_policy.bedrock_logging]
}
