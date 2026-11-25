# Phase 2 setup checklist

## For today (Day 1)

| Check | Command | You need |
|---|---|---|
| Python 3.11 or newer | `python --version` | Same as Phase 1 |
| Node.js 20 or newer | `node --version` | Install the LTS version from nodejs.org if missing |
| Git and Claude Code | `git --version` · `claude --version` | Same as Phase 1 |
| OpenRouter key | in `.env` | Same key as Phase 1 |

Then, in the new repository `fde-engagement/`:

1. `python -m venv .venv`, then activate it
2. `pip install -r backend/requirements.txt`
3. `cd frontend`, then `npm install`, then `npx playwright install chromium`
4. Copy `.env.example` to `.env` and add your OpenRouter key

## Before Day 5 (start this week: approvals can take a few days)

- Create an AWS account (free tier) with multi-factor authentication on the root user.
- In **Billing → Budgets**, create a monthly budget of USD 20 with an email alert.
- Open the **Amazon Bedrock** console in the **Europe (London) eu-west-2** region once. If it asks you to submit use-case details for Anthropic models, do it now.

## Before Day 8

- Create a free Slack workspace for yourself; you will add a test app to it.

## Your laptop

16 GB of RAM is recommended from Week 2, when the client environment runs several containers. Docker Desktop must be installed (Phase 1, Day 15).
