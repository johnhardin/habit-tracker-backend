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
6. The email contains an "I did it" button — clicking it hits the complete Lambda via API Gateway with a JWT authorizer; the Lambda reads your identity from the token, not the URL
7. The complete Lambda writes a completion record to DynamoDB
8. Every Sunday, the weekly Lambda scans the past 7 days of completions and sends a summary email

## DynamoDB Single-Table Design

All data lives in one table (`habit-tracker`) using a composite key pattern:

| Record type | Partition key (userId) | Sort key (sk) |
|---|---|---|
| Habit definition | `fakhri` | `HABIT#morning-workout` |
| Completion record | `fakhri` | `COMPLETION#2026-04-15#morning-workout` |

This pattern allows efficient querying by prefix — fetching all habits uses `begins_with(sk, 'HABIT#')`, fetching completions for a specific date uses `begins_with(sk, 'COMPLETION#2026-04-15')`.

## API Endpoints

Base URL: `https://<api-gateway-id>.execute-api.ap-southeast-1.amazonaws.com`

All routes require a Cognito JWT in the `Authorization` header. The user identity (`sub` claim) is extracted server-side — no `userId` is accepted from the client.

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

### Mark habit as complete (used by email link)
```
GET /complete?habitId={habitId}&date={YYYY-MM-DD}
Authorization: Bearer <jwt>
```

The `userId` is read from the JWT `sub` claim — it is not accepted as a query parameter.

## Lambda Functions

### habit-tracker-notify
Runs every hour via EventBridge. For each habit in DynamoDB it checks:
1. Does today match the habit's schedule? (daily/weekdays/weekends/specific days)
2. Does the current hour match the habit's reminder time? (converted from Jakarta UTC+7 to UTC)
3. Is there already a completion record for today?

If all checks pass, sends a reminder email via SES with an "I did it" link.

### habit-tracker-complete
Triggered by API Gateway when the user clicks "I did it" in the email. The route has a JWT authorizer — the `userId` is read from the token's `sub` claim, not from query parameters. Writes a `COMPLETION#` record to DynamoDB.

### habit-tracker-weekly
Runs every Sunday via EventBridge. Scans all habits and their completion records for the past 7 days, calculates completion rate per habit and overall, then sends a summary email.

### habit-tracker-api
Handles CRUD operations for habits via API Gateway (GET, POST, DELETE). All routes are protected by a JWT authorizer — `userId` is always sourced from the token's `sub` claim.

## Deployment

### Prerequisites
- AWS account with free tier
- AWS CLI configured (`aws configure`)
- Custom domain with DNS access (for SES domain verification)
- Python 3.12
- Cognito User Pool (for JWT issuance)

### Setup

**1. Create DynamoDB table**
```bash
aws dynamodb create-table \
  --table-name habit-tracker \
  --attribute-definitions \
    AttributeName=userId,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=userId,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-1
```

**2. Create IAM role**

Create a role named `habit-tracker-lambda-role` with these policies:
- `AmazonDynamoDBFullAccess`
- `AmazonSESFullAccess`
- `CloudWatchLogsFullAccess`

**3. Deploy Lambda functions**

For each file in `lambda/`:
```bash
zip function.zip lambda/notify.py
aws lambda create-function \
  --function-name habit-tracker-notify \
  --runtime python3.12 \
  --role arn:aws:iam::<account-id>:role/habit-tracker-lambda-role \
  --handler notify.lambda_handler \
  --zip-file fileb://function.zip \
  --region ap-southeast-1
```

**4. Set up SES domain**

Verify your domain in SES so emails land in inbox instead of spam.

In SES Console → Verified identities → Create identity → Domain:
- Select **Easy DKIM** with **RSA_2048_BIT** signing key
- SES will generate 3 CNAME records — add them to your DNS

Add these records to your DNS manually:

| Type | Name | Value |
|---|---|---|
| CNAME | *(provided by SES × 3)* | *(provided by SES)* |
| TXT | `@` | `v=spf1 include:amazonses.com ~all` |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:you@gmail.com` |

Wait for SES to show the domain as **Verified**, then set `FROM_EMAIL` in `notify.py` and `weekly.py`:
```python
FROM_EMAIL = 'noreply@yourdomain.com'
```

**5. Create Cognito User Pool**

Create a User Pool and an App Client — choose **Single-page application (SPA)** type (no client secret). Note the User Pool ID and the issuer URL:
```
https://cognito-idp.ap-southeast-1.amazonaws.com/<user-pool-id>
```

**6. Create API Gateway**

Create an HTTP API and attach a JWT authorizer using the Cognito issuer URL and the App Client ID as the audience.

Add these routes integrated with `habit-tracker-api` Lambda, all protected by the JWT authorizer:
- `GET /habits`
- `POST /habits`
- `DELETE /habits`

Add the `/complete` route integrated with `habit-tracker-complete` Lambda, also protected by the JWT authorizer:
- `GET /complete`

Configure CORS at the **API level** (not via a route) — go to API → Configuration → CORS:

| Field | Value |
|---|---|
| Allow origin | `https://yourdomain.com` |
| Allow headers | `Content-Type,Authorization` |
| Allow methods | `GET,POST,DELETE,OPTIONS` |
| Max age | `300` |

**7. Set EventBridge schedules**

| Schedule | Cron | Lambda |
|---|---|---|
| Hourly reminder | `0 * * * ? *` | `habit-tracker-notify` |
| Weekly summary | `0 22 ? * SUN *` | `habit-tracker-weekly` |

Both use Asia/Jakarta timezone.

## Environment Notes

- All times stored in Jakarta timezone (UTC+7)
- **SES is in sandbox mode** — reminder emails can only be sent to email addresses individually verified in SES Console → Verified identities. This project is intended for personal use; new users who want to try it must have their email verified in SES first
- Free tier covers this project comfortably — estimated cost after free tier: ~$0.01/month for a single user

## Frontend
**Live Demo:** habit.johnhardin.site

See the [habit-tracker-frontend](https://github.com/johnhardin/habit-tracker-frontend) repository for the dashboard source.