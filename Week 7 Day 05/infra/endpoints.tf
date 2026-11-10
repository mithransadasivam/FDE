# Private endpoints (AWS PrivateLink): calls to Bedrock and Secrets Manager never leave the VPC.
# With private DNS on, the code calls the usual bedrock-runtime.eu-west-2.amazonaws.com name
# and it resolves to the endpoint's private address: no code change.

locals {
  # The ARN the function may invoke. A bare model ID is a foundation model in this Region;
  # an ID with a geo or global prefix ("eu.", "global.") is an inference profile.
  in_region_model = length(regexall("^(eu|us|apac|au|jp|ca|in|global)\\.", var.model_id)) == 0
  foundation_model_arn  = "arn:aws:bedrock:${var.region}::foundation-model/${var.model_id}"
  inference_profile_arn = "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.model_id}"
  model_arn             = local.in_region_model ? local.foundation_model_arn : local.inference_profile_arn
  guardrail_arns = "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:guardrail/*"
}

resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.pilot.id
  service_name        = "com.amazonaws.${var.region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [aws_subnet.private.id]
  security_group_ids  = [aws_security_group.endpoints.id]

  # Without a policy, an endpoint allows every action on every model. This one allows only the pilot's model and guardrail.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PilotModelOnly"
        Effect    = "Allow"
        Principal = "*"
        Action    = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource  = [local.model_arn]
      },
      {
        Sid       = "PilotGuardrails"
        Effect    = "Allow"
        Principal = "*"
        Action    = ["bedrock:ApplyGuardrail"]
        Resource  = [local.guardrail_arns]
      }
    ]
  })
  tags = {
    Name = "uc1-pilot-bedrock-runtime"
  }
}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.pilot.id
  service_name        = "com.amazonaws.${var.region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = [aws_subnet.private.id]
  security_group_ids  = [aws_security_group.endpoints.id]
  tags = {
    Name = "uc1-pilot-secretsmanager"
  }
}
