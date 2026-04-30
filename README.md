# Habit Tracker Backend

A serverless habit tracking system built on AWS. The system sends daily email reminders for each habit, lets you mark habits as complete directly from the email, and sends a weekly summary every Sunday.

## Architecture

```
Dashboard (HTML/S3)
        │
        ▼
Cognito User Pool
(JWT issuer)
        │
        ▼
API Gateway (JWT Authorizer) ─────────────┐
        │                                 │
        ▼                                 ▼
habit-tracker-api Lambda          habit-tracker-complete Lambda
(add, get, delete habits)         (mark habit as done)
        │                                 │
        ▼                                 ▼
    DynamoDB ◄────────────────────────────┘
    (habit-tracker table)
        ▲
        │
EventBridge (cron: hourly)
        │
        ▼
habit-tracker-notify Lambda
(sends reminder emails via SES)
        │
        ▼
EventBridge (cron: every Sunday)
        │
        ▼
habit-tracker-weekly Lambda
(sends weekly summary email via SES)
```

## AWS Services Used

- **Lambda** — business logic, runs serverless on demand
- **API Gateway** — public HTTP endpoints for the dashboard and email links
- **Cognito User Pool** — user authentication and JWT token issuance
- **DynamoDB** — single-table design storing habits and completions
- **SES (Simple Email Service)** — sends reminder and summary emails
- **EventBridge** — cron schedulers that trigger Lambda automatically
- **IAM** — role-based permissions for Lambda to access DynamoDB and SES

## How It Works

1. You sign in through the dashboard — Cognito issues a JWT token
2. You add a habit through the dashboard with a name, email, schedule, and optional reminder time; the JWT is sent as the `Authorization` header and the API identifies you from its `sub` claim
3. EventBridge triggers the notify Lambda every hour
4. The notify Lambda checks each habit's schedule and reminder time against the current Jakarta time
5. If it's time to remind and the habit isn't completed yet, an email is sent via SES
6. The email contains an "I did it" button — clicking it hits the complete Lambda via API Gateway
7. The complete Lambda writes a completion record to DynamoDB
8. Every Sunday, the weekly Lambda scans the past 7 days of completions and sends a summary email

## DynamoDB Single-Table Design

All data lives in one table (`habit-tracker`) using a composite key pattern:

| Record type | Partition key (userId) | Sort key (sk) |
|---|---|---|
| Habit definition | `a1b2c3d4-e5f6-...` | `HABIT#morning-workout` |
| Completion record | `a1b2c3d4-e5f6-...` | `COMPLETION#2026-04-15#morning-workout` |

The `userId` is the Cognito `sub` claim from the JWT token — a UUID assigned by Cognito when the user signs up. This pattern allows efficient querying by prefix — fetching all habits uses `begins_with(sk, 'HABIT#')`, fetching completions for a specific date uses `begins_with(sk, 'COMPLETION#2026-04-15')`.

## API Endpoints

Base URL: `https://<api-gateway-id>.execute-api.ap-southeast-1.amazonaws.com`

All `/habits` routes require a Cognito JWT in the `Authorization` header. The `/complete` route has no JWT authorizer and is called directly from email links.

### Get all habits
```
GET /habits
Authorization: Bearer <jwt>
```

### Add a habit
```
POST /habits
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "name": "Morning Workout",
  "email": "you@gmail.com",
  "schedule": "daily",
  "reminderTime": "07:00"
}
```

Schedule options:
- `daily` — every day
- `weekdays` — Monday to Friday
- `weekends` — Saturday and Sunday
- `specific:Mon,Wed,Fri` — specific days

### Delete a habit
```
DELETE /habits?habitId={habitId}
Authorization: Bearer <jwt>
```

### Get completions for a date range
```
GET /completions?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
Authorization: Bearer <jwt>
```

### Mark habit as complete (used by email link)
```
GET /complete?userId={userId}&habitId={habitId}&date={YYYY-MM-DD}
```

This route has no JWT authorizer — it is called directly from an email link where no session exists. The `userId`, `habitId`, and `date` are all passed as query parameters by the notify Lambda when it builds the email link.

## Lambda Functions

### habit-tracker-notify
Runs every hour via EventBridge. For each habit in DynamoDB it checks:
1. Does today match the habit's schedule? (daily/weekdays/weekends/specific days)
2. Does the current hour match the habit's reminder time? (converted from Jakarta UTC+7 to UTC)
3. Is there already a completion record for today?

If all checks pass, sends a reminder email via SES with an "I did it" link.

### habit-tracker-complete
Triggered by API Gateway when the user clicks "I did it" in the email. The route has **no JWT authorizer** — the email link is a plain URL with no session context. The `userId`, `habitId`, and `date` are read from query parameters. Writes a `COMPLETION#` record to DynamoDB.

### habit-tracker-weekly
Runs every Sunday via EventBridge. Scans all habits and their completion records for the past 7 days, calculates completion rate per habit and overall, then sends a summary email.

### habit-tracker-api
Handles CRUD operations for habits via API Gateway (GET, POST, DELETE). All routes are protected by a JWT authorizer — `userId` is always sourced from the token's `sub` claim.

## Deployment

Infrastructure is managed with Terraform. All 29 AWS resources (Lambda, API Gateway, DynamoDB, Cognito, EventBridge, IAM) are provisioned from a single command.

### Prerequisites
- AWS account with free tier
- AWS CLI configured (`aws configure`)
- Terraform installed ([install guide](https://developer.hashicorp.com/terraform/install))
- Custom domain with SES verified (DKIM, SPF, DMARC) — see SES setup below
- Python 3.12

### SES Domain Setup (one-time, manual)

SES domain verification is not managed by Terraform since DKIM DNS records must be added manually through your DNS provider.

In SES Console → Verified identities → Create identity → Domain:
- Select **Easy DKIM** with **RSA_2048_BIT** signing key
- SES will generate 3 CNAME records — add them to your DNS

Add these records to your DNS:

| Type | Name | Value |
|---|---|---|
| CNAME | *(provided by SES × 3)* | *(provided by SES)* |
| TXT | `@` | `v=spf1 include:amazonses.com ~all` |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:you@gmail.com` |

Wait for SES to show the domain as **Verified**, then update `FROM_EMAIL` in `notify.py` and `weekly.py`:
```python
FROM_EMAIL = 'noreply@yourdomain.com'
```

### Deploy with Terraform

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

After apply, Terraform prints the values you need to configure the frontend:

```
api_gateway_url       = "https://xxxxxxxxxx.execute-api.ap-southeast-1.amazonaws.com"
cognito_user_pool_id  = "ap-southeast-1_xxxxxxxxx"
cognito_app_client_id = "xxxxxxxxxxxxxxxxxxxxxxxxxx"
cognito_issuer_url    = "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_xxx"
```

Update these values in the frontend config, then redeploy the frontend.

### Updating Lambda code

Edit any file in `lambda/` then run:

```bash
cd terraform && terraform apply
```

Terraform detects the change, rezips the file, and redeploys only the affected Lambda.

### Tear down

```bash
cd terraform && terraform destroy
```

Deletes all 29 resources from AWS. SES domain verification is preserved since it is not managed by Terraform.

## Environment Notes

- All times stored in Jakarta timezone (UTC+7)
- **SES is in sandbox mode** — reminder emails can only be sent to email addresses individually verified in SES Console → Verified identities. This project is intended for personal use; new users who want to try it must have their email verified in SES first
- Free tier covers this project comfortably — estimated cost after free tier: ~$0.01/month for a single user

## Frontend
**Live Demo:** habit.johnhardin.site

See the [habit-tracker-frontend](https://github.com/johnhardin/habit-tracker-frontend) repository for the dashboard source.
