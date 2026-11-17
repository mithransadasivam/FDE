# The analysts' password for the pilot screen. Terraform generates it; nobody types or emails it.
# Read it with:  aws secretsmanager get-secret-value --secret-id <secret_arn output> --query SecretString --output text

resource "random_password" "analyst" {
  length  = 24
  special = false
}

resource "random_id" "suffix" {
  byte_length = 3
}

resource "aws_secretsmanager_secret" "pilot" {
  name                    = "uc1-pilot/analyst-password-${random_id.suffix.hex}"
  description             = "Password for the UC1 pilot screen (user: analyst)"
  recovery_window_in_days = 0 # the pilot is torn down daily: delete at once instead of after 30 days
}

resource "aws_secretsmanager_secret_version" "pilot" {
  secret_id     = aws_secretsmanager_secret.pilot.id
  secret_string = random_password.analyst.result
}
