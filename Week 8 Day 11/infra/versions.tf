# The UC1 pilot in the client's AWS account, London (eu-west-2). Day 5, starter template.
#
#   terraform init
#   terraform plan -out pilot.tfplan && terraform show -json pilot.tfplan > pilot.plan.json
#   python -m scripts.check_pilot            (from backend/: the bank's rules, checked on the plan)
#   terraform apply pilot.tfplan
#   terraform destroy                        (at the end of the day: the endpoints cost money every hour)

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      project    = "fde-uc1-pilot"
      owner      = var.owner
      course_day = "5"
    }
  }
}

data "aws_caller_identity" "current" {}
