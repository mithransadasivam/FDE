# Pilot teardown record

*Copy to docs/eval/TEARDOWN_RECORD.md. Fill it in after terraform destroy, with the commands' real output.*

**Date and time:** · **Account:** (last four digits only) · **Region:** eu-west-2

## 1. Destroy

- Command: `terraform destroy` in infra/
- Resources destroyed (the last line of the output):

## 2. Prove nothing is left

| Check | Command | Result |
|---|---|---|
| Terraform state is empty | `terraform state list` | |
| No VPC endpoints with the pilot's tag | `aws ec2 describe-vpc-endpoints --region eu-west-2 --filters Name=tag:project,Values=fde-uc1-pilot --query "VpcEndpoints[].VpcEndpointId"` | |
| No pilot function | `aws lambda get-function --function-name uc1-pilot --region eu-west-2` | |
| Invocation logging is off | `aws bedrock get-model-invocation-logging-configuration --region eu-west-2` | |

## 3. What the day cost

- From Billing and Cost Management → Bills (or Cost Explorer), yesterday's charges by service:

| Service | USD |
|---|---|
| | |

- Compared with the estimate on Pilot → Spend:

## 4. What you would do differently for the client's real account
