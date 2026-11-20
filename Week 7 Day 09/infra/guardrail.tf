# The guardrail, built from one policy file in guardrails/. The same file drives the scripted guardrail
# in backend/app/platform/guardrail.py, so what you test offline is what you deploy.

locals {
  guardrail = jsondecode(file("${path.module}/guardrails/${var.guardrail_policy}.json"))
}

resource "aws_bedrock_guardrail" "uc1" {
  name                      = "uc1-pilot"
  description               = local.guardrail.description
  blocked_input_messaging   = local.guardrail.blocked_input_messaging
  blocked_outputs_messaging = local.guardrail.blocked_outputs_messaging

  dynamic "content_policy_config" {
    for_each = length(local.guardrail.content_filters) > 0 ? [1] : []
    content {
      dynamic "filters_config" {
        for_each = local.guardrail.content_filters
        content {
          type            = filters_config.value.type
          input_strength  = filters_config.value.input_strength
          output_strength = filters_config.value.output_strength
        }
      }
      tier_config {
        tier_name = "CLASSIC" # STANDARD needs cross-Region guardrail inference: the text would leave London
      }
    }
  }

  dynamic "topic_policy_config" {
    for_each = length(local.guardrail.denied_topics) > 0 ? [1] : []
    content {
      dynamic "topics_config" {
        for_each = local.guardrail.denied_topics
        content {
          name       = topics_config.value.name
          definition = topics_config.value.definition
          examples   = topics_config.value.examples
          type       = "DENY"
        }
      }
      tier_config {
        tier_name = "CLASSIC"
      }
    }
  }

  dynamic "sensitive_information_policy_config" {
    for_each = length(local.guardrail.pii_entities) + length(local.guardrail.regexes) > 0 ? [1] : []
    content {
      dynamic "pii_entities_config" {
        for_each = local.guardrail.pii_entities
        content {
          type           = pii_entities_config.value.type
          action         = pii_entities_config.value.output_action
          input_action   = pii_entities_config.value.input_action
          output_action  = pii_entities_config.value.output_action
          input_enabled  = pii_entities_config.value.input_action != "NONE"
          output_enabled = pii_entities_config.value.output_action != "NONE"
        }
      }
      dynamic "regexes_config" {
        for_each = local.guardrail.regexes
        content {
          name           = regexes_config.value.name
          description    = regexes_config.value.description
          pattern        = regexes_config.value.pattern
          action         = regexes_config.value.output_action
          input_action   = regexes_config.value.input_action
          output_action  = regexes_config.value.output_action
          input_enabled  = regexes_config.value.input_action != "NONE"
          output_enabled = regexes_config.value.output_action != "NONE"
        }
      }
    }
  }
}

# A numbered, unchangeable version for the function to use. A new policy file makes a new version.
resource "aws_bedrock_guardrail_version" "uc1" {
  guardrail_arn = aws_bedrock_guardrail.uc1.guardrail_arn
  description   = "${var.guardrail_policy} ${substr(sha1(file("${path.module}/guardrails/${var.guardrail_policy}.json")), 0, 8)}"
}
