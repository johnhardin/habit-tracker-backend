# Habit Tracker Backend

Serverless AWS backend for a habit-tracking application. The system stores habits, sends reminder emails on a schedule, records completions from email links, and sends weekly summary emails.

This repository is the strongest cloud/DevOps part of the project. It demonstrates managed identity, serverless compute, NoSQL data modeling, scheduled automation, monitoring, and Infrastructure as Code.

## Architecture

```text
Static frontend
    |
    v
Cognito User Pool
    |
    v
API Gateway HTTP API ------------------------------+
    |                                              |
    | JWT auth on protected routes                 | public route for email clicks
    v                                              v
habit-tracker-api Lambda                  habit-tracker-complete Lambda
    |                                              |
    +--------------------------+-------------------+
                               |
                               v
                          DynamoDB
                               ^
                               |
                  +------------+-------------+
                  |                          |
                  v                          v
            EventBridge                 EventBridge
            hourly cron                 weekly cron
                  |                          |
                  v                          v
      habit-tracker-notify Lambda   habit-tracker-weekly Lambda
                  |                          |
                  v                          v
                 SES                        SES

CloudWatch alarms -> SNS topic -> email alert
```

## AWS services used

- `AWS Lambda` - API, reminder, completion, and summary logic
- `API Gateway HTTP API` - public API entry point
- `Amazon Cognito` - user sign-up, sign-in, and JWT issuance
- `Amazon DynamoDB` - habit and completion storage
- `Amazon SES` - reminder and weekly summary emails
- `Amazon EventBridge` - scheduled triggers
- `Amazon CloudWatch` - logs and alarms
- `Amazon SNS` - alarm notifications
- `IAM` - execution roles and service permissions
- `Terraform` - infrastructure provisioning

## Request and job flows

### 1. Authenticated dashboard flow

1. User signs in through Cognito.
2. The frontend sends the JWT in the `Authorization` header.
3. API Gateway validates the token with a JWT authorizer.
4. `habit-tracker-api` reads the Cognito `sub` claim from the request context.
5. The Lambda reads or writes habit data in DynamoDB.

### 2. Reminder flow

1. EventBridge runs `habit-tracker-notify` every hour.
2. The Lambda queries all `HABIT` items through the GSI.
3. For each habit, it checks:
   - whether today matches the schedule
   - whether the current UTC hour matches the stored Jakarta reminder hour
   - whether the habit has already been completed today
4. If all checks pass, it sends an SES email with a `/complete` link.

### 3. Completion flow

1. The user clicks the email link.
2. API Gateway routes `GET /complete` to `habit-tracker-complete`.
3. The Lambda writes a completion record into DynamoDB.

### 4. Weekly summary flow

1. EventBridge runs `habit-tracker-weekly` every Sunday.
2. The Lambda gathers the last 7 days of completion records.
3. It calculates per-habit and overall completion percentages.
4. It sends a summary email through SES.

## Repository layout

| Path | Purpose |
|---|---|
| `lambda/api.py` | Authenticated habit CRUD and completion queries |
| `lambda/complete.py` | Public completion endpoint used by email links |
| `lambda/notify.py` | Hourly reminder scheduler |
| `lambda/weekly.py` | Weekly summary scheduler |
| `terraform/` | AWS infrastructure definition |

## DynamoDB data model

The table name is `habit-tracker`.

Primary key:

- partition key: `userId`
- sort key: `sk`

Habit item example:

```json
{
  "userId": "cognito-sub-uuid",
  "sk": "HABIT#morning-workout-ab12",
  "habitId": "morning-workout-ab12",
  "name": "Morning Workout",
  "email": "you@example.com",
  "schedule": "daily",
  "recordType": "HABIT",
  "reminderTime": "07:00"
}
```

Completion item example:

```json
{
  "userId": "cognito-sub-uuid",
  "sk": "COMPLETION#2026-05-21#morning-workout-ab12",
  "habitId": "morning-workout-ab12",
  "date": "2026-05-21",
  "completedAt": "2026-05-21T01:05:00+00:00"
}
```

### Why this design works

- all user data is colocated under one partition key
- all habits can be queried with `begins_with(sk, 'HABIT#')`
- completion records in a date range can be queried lexicographically
- a GSI on `recordType` allows the notify job to find all habits across users

### Global Secondary Index

Terraform defines:

- `recordType-index` with partition key `recordType`

Only habit items write `recordType = "HABIT"`, so the notify Lambda can query all habits without scanning the full table.

## API surface

Base URL:

```text
https://<api-gateway-id>.execute-api.ap-southeast-1.amazonaws.com
```

Protected routes require:

```http
Authorization: Bearer <jwt>
```

### `GET /habits`

Returns all habits for the authenticated user.

### `POST /habits`

Creates a habit.

Example body:

```json
{
  "name": "Morning Workout",
  "email": "you@gmail.com",
  "schedule": "daily",
  "reminderTime": "07:00"
}
```

Supported schedule values:

- `daily`
- `weekdays`
- `weekends`
- `specific:Mon,Wed,Fri`

### `DELETE /habits?habitId={habitId}`

Deletes a habit definition for the authenticated user.

### `GET /completions?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD`

Returns completion records for the authenticated user in a date range.

### `GET /complete?userId={userId}&habitId={habitId}&date={YYYY-MM-DD}`

Public endpoint used by the email reminder link.

This route intentionally has no JWT authorizer because it must work from an inbox click where the user has no active browser session.

## Terraform-managed infrastructure

The Terraform configuration provisions:

- DynamoDB table and GSI
- Cognito user pool and app client
- API Gateway HTTP API
- JWT authorizer for protected routes
- four Lambda functions
- EventBridge schedules and permissions
- CloudWatch alarms
- SNS alert topic and email subscription

The Lambda packages are built with Terraform `archive_file` data sources, so a code change in `lambda/*.py` triggers a new ZIP hash and redeploys the changed function on `terraform apply`.

## Monitoring and alerts

Terraform provisions five CloudWatch alarms:

| Alarm | Metric | Threshold |
|---|---|---|
| `habit-tracker-api-errors` | Lambda `Errors` | `>= 1` in 5 minutes |
| `habit-tracker-complete-errors` | Lambda `Errors` | `>= 1` in 5 minutes |
| `habit-tracker-notify-errors` | Lambda `Errors` | `>= 1` in 5 minutes |
| `habit-tracker-weekly-errors` | Lambda `Errors` | `>= 1` in 5 minutes |
| `habit-tracker-apigw-5xx` | API Gateway `5xx` | `>= 1` in 5 minutes |

All alarms publish to an SNS topic, which then sends an email notification to the configured subscriber.

## Security notes

Current security properties:

- protected API routes are validated by API Gateway with Cognito-issued JWTs
- backend user identity comes from the JWT `sub` claim, not from client-supplied IDs
- the completion route is intentionally public because it is designed for email links

Current security gaps worth improving:

- Lambda execution currently uses AWS-managed `FullAccess` IAM policies, which are broader than needed
- the public `/complete` route is not signed or tokenized beyond query parameters
- CORS currently allows `*`

Those tradeoffs are acceptable for a personal learning project, but they should be tightened for a production or team environment.

## Deployment

### Prerequisites

- AWS account
- AWS CLI configured
- Terraform installed
- Python 3.12
- SES verified sender domain or email

### SES setup

SES verification is still a manual prerequisite. Verify the sender domain or email address in SES before sending reminders.

If using a domain identity, add the DKIM, SPF, and DMARC records that SES gives you, then update the sender address used by the Lambdas.

### Deploy

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

After apply, Terraform outputs:

- API Gateway base URL
- Cognito user pool ID
- Cognito app client ID
- Cognito issuer URL

Those frontend values must be copied into the config block in the frontend HTML files.

### Update Lambda code

```bash
cd terraform
terraform apply
```

Terraform recalculates the ZIP hash and updates only changed Lambda functions.

### Tear down

```bash
cd terraform
terraform destroy
```

## Timezone and environment assumptions

- reminder times are entered in Jakarta time (`UTC+7`)
- the notify Lambda converts Jakarta reminder hours to UTC for scheduling
- the weekly EventBridge rule runs at `cron(0 22 ? * SUN *)`, which aligns with Monday 05:00 Jakarta time, not midnight Sunday local time

That last point is worth revisiting if the intent is a true end-of-week summary in Jakarta time.

## Known limitations

- weekly summary logic scans habits rather than using the `recordType-index` query pattern used by the notify Lambda
- reminder and summary sender addresses are hardcoded in the Lambda source
- Terraform state in this workspace is local and should move to remote state for team or production use
- IAM policies are not least privilege yet
- the completion route is write-only; there is no un-complete endpoint

## Frontend

([Habit-tracker-frontend](https://github.com/johnhardin/habit-tracker-frontend)).
