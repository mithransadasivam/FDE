output "function_url" {
  description = "Open this, sign in as analyst with the password from Secrets Manager."
  value       = aws_lambda_function_url.pilot.function_url
}

output "secret_arn" {
  value = aws_secretsmanager_secret.pilot.arn
}

output "guardrail_id" {
  value = aws_bedrock_guardrail.uc1.guardrail_id
}

output "guardrail_version" {
  value = aws_bedrock_guardrail_version.uc1.version
}

output "model_id" {
  value = var.model_id
}

output "region" {
  value = var.region
}
