variable "region" {
  description = "Where everything runs. Helen's rule: customer data stays in the UK, so London."
  type        = string
  default     = "eu-west-2"
}

variable "owner" {
  description = "Your name or initials, added as a tag to every resource."
  type        = string
}

variable "alert_email" {
  description = "Where the budget alerts go."
  type        = string
}

variable "model_id" {
  description = "The Bedrock model ID the pilot calls. The default is ADR-001's choice: check where it runs before you deploy."
  type        = string
  default     = "eu.anthropic.claude-haiku-5-5"
}

variable "guardrail_policy" {
  description = "The guardrail policy file in guardrails/, without .json."
  type        = string
  default     = "uc1_v1"
}

variable "budget_usd" {
  description = "Monthly budget for this account, in US dollars. Martin agreed USD 20 for the pilot week."
  type        = number
  default     = 20
}

variable "lambda_zip" {
  description = "The package built by python -m scripts.build_lambda."
  type        = string
  default     = "build/lambda.zip"
}
