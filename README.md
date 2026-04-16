# Habit Tracker Backend

A serverless habit tracking system built on AWS. The system sends daily email reminders for each habit, lets you mark habits as complete directly from the email, and sends a weekly summary every Sunday.

## Architecture

```
Dashboard (HTML/S3)
        │
        ▼
API Gateway ──────────────────────────────┐
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
- **DynamoDB** — single-table design storing habits and completions
- **SES (Simple Email Service)** — sends reminder and summary emails
- **EventBridge** — cron schedulers that trigger Lambda automatically
- **IAM** — role-based permissions for Lambda to access DynamoDB and SES

## How It Works

1. You add a habit through the dashboard with a name, email, schedule, and optional reminder time
2. EventBridge triggers the notify Lambda every hour
3. The notify Lambda checks each habit's schedule and reminder time against the current Jakarta time
4. If it's time to remind and the habit isn't completed yet, an email is sent via SES
5. The email contains an "I did it" button — clicking it hits the complete Lambda via API Gateway
6. The complete Lambda writes a completion record to DynamoDB
7. Every Sunday, the weekly Lambda scans the past 7 days of completions and sends a summary email

## DynamoDB Single-Table Design

All data lives in one table (`habit-tracker`) using a composite key pattern:

| Record type | Partition key (userId) | Sort key (sk) |
|---|---|---|
| Habit definition | `fakhri` | `HABIT#morning-workout` |
| Completion record | `fakhri` | `COMPLETION#2026-04-15#morning-workout` |

This pattern allows efficient querying by prefix — fetching all habits uses `begins_with(sk, 'HABIT#')`, fetching completions for a specific date uses `begins_with(sk, 'COMPLETION#2026-04-15')`.

## API Endpoints

Base URL: `https://<api-gateway-id>.execute-api.ap-southeast-1.amazonaws.com`

### Get all habits
```
GET /habits?userId={userId}
```

### Add a habit
```
POST /habits
Content-Type: application/json

{
  "userId": "fakhri",
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
DELETE /habits?userId={userId}&habitId={habitId}
```

### Mark habit as complete (used by email link)
```
GET /complete?userId={userId}&habitId={habitId}&date={YYYY-MM-DD}
```

## Lambda Functions

### habit-tracker-notify
Runs every hour via EventBridge. For each habit in DynamoDB it checks:
1. Does today match the habit's schedule? (daily/weekdays/weekends/specific days)
2. Does the current hour match the habit's reminder time? (converted from Jakarta UTC+7 to UTC)
3. Is there already a completion record for today?

If all checks pass, sends a reminder email via SES with an "I did it" link.

### habit-tracker-complete
Triggered by API Gateway when the user clicks "I did it" in the email. Writes a `COMPLETION#` record to DynamoDB.

### habit-tracker-weekly
Runs every Sunday via EventBridge. Scans all habits and their completion records for the past 7 days, calculates completion rate per habit and overall, then sends a summary email.

### habit-tracker-api
Handles CRUD operations for habits via API Gateway. Supports GET, POST, and DELETE.

## Deployment

### Prerequisites
- AWS account with free tier
- AWS CLI configured (`aws configure`)
- SES email verified in ap-southeast-1
- Python 3.12

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

**4. Create API Gateway**

Create an HTTP API with these routes, all integrated with `habit-tracker-api` Lambda:
- `GET /habits`
- `POST /habits`
- `DELETE /habits`
- `OPTIONS /{proxy+}`

Enable CORS with `Access-Control-Allow-Origin: *`.

**5. Set EventBridge schedules**

| Schedule | Cron | Lambda |
|---|---|---|
| Hourly reminder | `0 * * * ? *` | `habit-tracker-notify` |
| Weekly summary | `0 22 ? * SUN *` | `habit-tracker-weekly` |

Both use Asia/Jakarta timezone.

## Environment Notes

- All times stored in Jakarta timezone (UTC+7)
- SES starts in sandbox mode — only verified emails can receive messages
- Request SES production access to send to any email address
- Free tier covers this project comfortably — estimated cost after free tier: ~$0.01/month for a single user

## Frontend
**Live Demo:** habit.johnhardin.site

See the [habit-tracker-frontend](https://github.com/johnhardin/habit-tracker-frontend) repository for the dashboard source.