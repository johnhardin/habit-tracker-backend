import boto3
from datetime import datetime, timezone, timedelta

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
ses = boto3.client('ses', region_name='ap-southeast-1')
table = dynamodb.Table('habit-tracker')

FROM_EMAIL = '<EMAIL_ADDRESS>'
JAKARTA_OFFSET = timedelta(hours=7)

def lambda_handler(event, context):
    try:
        now_utc = datetime.now(timezone.utc)
        now_jakarta = now_utc + JAKARTA_OFFSET

        current_hour_utc = now_utc.strftime('%H')
        today_jakarta = now_jakarta.strftime('%Y-%m-%d')
        day_of_week = now_jakarta.strftime('%A')

        print(f'UTC: {now_utc.strftime("%Y-%m-%d %H:%M")} | Jakarta: {now_jakarta.strftime("%Y-%m-%d %H:%M")} | Day: {day_of_week}')

        response = table.scan(
            FilterExpression='begins_with(sk, :prefix)',
            ExpressionAttributeValues={':prefix': 'HABIT#'}
        )

        habits = response.get('Items', [])

        if not habits:
            print('No habits found')
            return {'statusCode': 200, 'body': 'No habits found'}

        sent = 0
        for habit in habits:
            user_id = habit['userId']
            habit_id = habit['habitId']
            habit_name = habit['name']
            user_email = habit['email']

            # Check schedule (weekdays/weekends/daily/specific)
            schedule = habit.get('schedule', 'daily')

            if schedule == 'weekdays' and day_of_week in ['Saturday', 'Sunday']:
                print(f'Skipping {habit_name} — weekdays only, today is {day_of_week}')
                continue

            if schedule == 'weekends' and day_of_week not in ['Saturday', 'Sunday']:
                print(f'Skipping {habit_name} — weekends only, today is {day_of_week}')
                continue

            if schedule.startswith('specific:'):
                allowed_days = schedule.replace('specific:', '').split(',')
                # Convert full day name to 3-letter abbreviation
                day_abbr = day_of_week[:3]
                if day_abbr not in allowed_days:
                    print(f'Skipping {habit_name} — specific days {allowed_days}, today is {day_abbr}')
                    continue

            # Check reminder time
            reminder_time = habit.get('reminderTime', None)
            if reminder_time:
                reminder_hour_jakarta = int(reminder_time.split(':')[0])
                reminder_hour_utc = (reminder_hour_jakarta - 7) % 24
                if str(reminder_hour_utc).zfill(2) != current_hour_utc:
                    print(f'Skipping {habit_name} — set for Jakarta {reminder_time}, UTC {reminder_hour_utc:02d}:00, current UTC {current_hour_utc}:00')
                    continue

            # Check if already completed today (using Jakarta date)
            completion_sk = f'COMPLETION#{today_jakarta}#{habit_id}'
            existing = table.get_item(
                Key={'userId': user_id, 'sk': completion_sk}
            ).get('Item')

            if existing:
                print(f'Already completed: {habit_name}')
                continue

            done_link = f'https://61y3ffttr2.execute-api.ap-southeast-1.amazonaws.com/complete?userId={user_id}&habitId={habit_id}&date={today_jakarta}'
            send_reminder_email(user_email, habit_name, done_link, today_jakarta)
            sent += 1
            print(f'Sent reminder for {habit_name} to {user_email}')

        return {'statusCode': 200, 'body': f'Sent {sent} reminders'}

    except Exception as e:
        print(f'Error: {str(e)}')
        return {'statusCode': 500, 'body': str(e)}

def send_reminder_email(to_email, habit_name, done_link, today):
    subject = f'Reminder: {habit_name}'
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 500px; margin: 40px auto; color: #333;">
        <h2 style="color: #2c3e50;">Hey, time for your habit!</h2>
        <p style="font-size: 18px;">📌 <strong>{habit_name}</strong></p>
        <p style="color: #666;">Today: {today}</p>
        <br>
        <a href="{done_link}"
           style="background-color: #27ae60; color: white; padding: 14px 28px;
                  text-decoration: none; border-radius: 6px; font-size: 16px;">
            ✅ I did it!
        </a>
        <br><br>
        <p style="color: #999; font-size: 13px;">Click the button once you've completed your habit.</p>
    </body>
    </html>
    """

    ses.send_email(
        Source=FROM_EMAIL,
        Destination={'ToAddresses': [to_email]},
        Message={
            'Subject': {'Data': subject},
            'Body': {'Html': {'Data': body_html}}
        }
    )