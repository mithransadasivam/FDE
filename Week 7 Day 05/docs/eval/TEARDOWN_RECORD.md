# Pilot teardown record

**Date and time:** 10 November 2026, about 13:55 (machine local time) · **Account:** ending 4332 · **Region:** eu-west-2

**Honest summary:** I could not run the four proof commands as written, and I have not pasted any output I did not get. Terraform and the AWS CLI are not installed on this machine, there is no Terraform state anywhere in the repository, and the AWS account's organisation policy denies every read call I tried. The evidence below is what I could really observe. The checks must be run by the student in the lab account (or by the trainer) to complete this record.

## 1. Destroy

- Command: `terraform destroy` in infra/ — **not run.**
- Resources destroyed (the last line of the output): **none, because nothing was applied from this machine.** Evidence:
  - `terraform` is not on the PATH (`terraform: command not found`).
  - No `terraform.tfstate`, `.terraform/`, `terraform.tfvars`, `pilot.tfplan` or `pilot.plan.json` exists anywhere under the project. Only the `.tf` files and `terraform.tfvars.example` are in infra/.
  - One trace of Terraform use does exist: `infra/.terraform.lock.hcl`, which `terraform init` creates. So Terraform was initialised in infra/ at some point, but it left no `.terraform/` folder and no state, which is consistent with no apply (or with files removed afterwards; I cannot tell which).
  - The Lambda package (`infra/build/lambda.zip`) was never built: infra/build does not exist.
  - Git history for this project stops at "Day 5 start"; no commit applies the pilot.
  - Rule 8 in CLAUDE.md says `terraform apply` and `terraform destroy` are never run without showing the plan and asking, and I was not asked to apply or destroy, so I did not install Terraform to do it.

## 2. Prove nothing is left

| Check | Command | Result |
|---|---|---|
| Terraform state is empty | `terraform state list` | **Not run** (Terraform not installed). There is no state file at all, which is what an empty state means here. |
| No VPC endpoints with the pilot's tag | `aws ec2 describe-vpc-endpoints --region eu-west-2 --filters Name=tag:project,Values=fde-uc1-pilot --query "VpcEndpoints[].VpcEndpointId"` | **Could not be checked.** The AWS CLI is not installed, so I made the same call with boto3 (`describe_vpc_endpoints`, same tag filter, eu-west-2). Real output: `UnauthorizedOperation - You are not authorized to perform this operation. User: arn:aws:iam::...4332:user/fde-student is not authorized to perform: ec2:DescribeVpcEndpoints with an explicit deny in a service control policy` |
| No pilot function | `aws lambda get-function --function-name uc1-pilot --region eu-west-2` | **Could not be checked.** boto3 `get_function` for uc1-pilot returned: `AccessDeniedException - User: arn:aws:iam::...4332:user/fde-student is not authorized to perform: lambda:GetFunction on resource: arn:aws:lambda:eu-west-2:...4332:function:uc1-pilot with an explicit deny in a service control policy`. This is not `ResourceNotFoundException`, so it proves nothing about whether the function exists. |
| Invocation logging is off | `aws bedrock get-model-invocation-logging-configuration --region eu-west-2` | **Could not be checked.** boto3 returned: `AccessDeniedException - ... is not authorized to perform: bedrock:GetModelInvocationLoggingConfiguration ... with an explicit deny in a service control policy` |

I also tried `ec2:DescribeVpcs` (tag project=fde-uc1-pilot) and `lambda:ListFunctions`; both were denied by the same service control policy. That policy is set at the organisation level, so it looks like the course lab account has been locked after class; I cannot change it and did not try to.

What this means: **I have not proved the pilot is gone, and I have not proved it is still there.** All I can show is that nothing was applied from this machine. If someone else applied the pilot from another machine or session, its resources could still exist, and the two private endpoints would keep costing about USD 0.48 a day.

To finish the record, run these from a shell that has Terraform and an AWS identity allowed to read (not the locked student user), and paste the real output over the "Could not be checked" cells:

```
cd infra
terraform state list
aws ec2 describe-vpc-endpoints --region eu-west-2 --filters Name=tag:project,Values=fde-uc1-pilot --query "VpcEndpoints[].VpcEndpointId"
aws lambda get-function --function-name uc1-pilot --region eu-west-2
aws bedrock get-model-invocation-logging-configuration --region eu-west-2
```

Proved when: no output; `[]`; `ResourceNotFoundException`; no `loggingConfig`. The last check matters because invocation logging is an account-and-Region setting: if it were left on, every Bedrock call in the account would keep writing logs.

## 3. What the day cost

- From Billing and Cost Management → Bills (or Cost Explorer), yesterday's charges by service: **not read.** Billing is a console page and the Billing API is also covered by the lock; I have no bill to quote and will not estimate one as if it were real. To fill in tomorrow morning: Billing and Cost Management → Bills → charges by service for the day.

| Service | USD |
|---|---|
| Amazon VPC (two interface endpoints) | not read from the bill |
| Amazon Bedrock | not read from the bill |
| Lambda, Secrets Manager, CloudWatch | not read from the bill |

- Compared with the estimate on Pilot → Spend: not compared. What I can say from the Terraform files: the two private endpoints cost about USD 0.48 a day whether or not anyone calls the model (a month left running is about USD 15 for nothing); the model itself costs nothing when nobody calls it.

## 4. What you would do differently for the client's real account

- Run apply and destroy from a pipeline with a plan review, so a destroy always leaves a recorded "Resources: N destroyed" line and the four proof outputs, instead of depending on one person's laptop.
- Keep the Terraform state in an encrypted, versioned bucket with locking, so a teardown can be proved from state and not from "there is no file on my machine". Today the state is local, which is why I cannot show it was ever applied or destroyed.
- Give the checks a read-only role, separate from the one that applies, so verification is not blocked by the same policy that limits the student user.
- Send budget alerts to the bank's FinOps mailbox and have Martin review the budget action before it is switched on.
- Use two Availability Zones and single sign-on, not one shared student user.
- Tag every resource with owner and project (already done in this Terraform) and run a weekly "anything tagged fde-uc1-pilot" sweep, so a forgotten pilot is found by a check, not by a bill.
