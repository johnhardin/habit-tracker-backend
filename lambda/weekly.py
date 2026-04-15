import boto3
from datetime import datetime, timezone, timedelta
from collections import defaultdict

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
ses = boto3.client('ses', region_name='ap-southeast-1')
table = dynamodb.Table('habit-tracker')

FROM_EMAIL = 'chocobibi.ff@gmail.com'

def lambda_handler(event, context):
    try:
        today = datetime.now(timezone.utc)
        week_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') 
                      for i in range(7)]

        # Get all habits
        habits_response = table.scan(
            FilterExpression='begins_with(sk, :prefix)',
            ExpressionAttributeValues={':prefix': 'HABIT#'}
        )
        habits = habits_response.get('Items', [])

        if not habits:
            print('No habits found')
            return {'statusCode': 200, 'body': 'No habits found'}

        # Group habits by user
        users = defaultdict(list)
        for habit in habits:
            users[habit['userId']].append(habit)

        for user_id, user_habits in users.items():
            user_email = user_habits[0]['email']
            habit_stats = []

            for habit in user_habits:
                habit_id = habit['habitId']
                habit_name = habit['name']
                completed_days = []

                for date in week_dates:
                    sk = f'COMPLETION#{date}#{habit_id}'
                    result = table.get_item(
                        Key={'userId': user_id, 'sk': sk}
                    ).get('Item')
                    if result:
                        completed_days.append(date)

                total = len(week_dates)
                completed = len(completed_days)
                missed = total - completed
                percentage = round((completed / total) * 100)

                habit_stats.append({
                    'name': habit_name,
                    'completed': completed,
                    'missed': missed,
                    'percentage': percentage,
                    'total': total
                })

            send_weekly_email(user_email, habit_stats, week_dates)

        return {'statusCode': 200, 'body': 'Weekly summaries sent'}

    except Exception as e:
        print(f'Error: {str(e)}')
        return {'statusCode': 500, 'body': str(e)}

def send_weekly_email(to_email, habit_stats, week_dates):
    start_date = week_dates[-1]
    end_date = week_dates[0]

    rows = ''
    for stat in habit_stats:
        color = '#27ae60' if stat['percentage'] >= 70 else '#e67e22' if stat['percentage'] >= 40 else '#e74c3c'
        emoji = '🟢' if stat['percentage'] >= 70 else '🟡' if stat['percentage'] >= 40 else '🔴'
        rows += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #eee;">{emoji} {stat['name']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; text-align:center; color:#27ae60;">
                {stat['completed']}/{stat['total']}
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; text-align:center; color:#e74c3c;">
                {stat['missed']}
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; text-align:center;">
                <strong style="color:{color};">{stat['percentage']}%</strong>
            </td>
        </tr>
        """

    total_completed = sum(s['completed'] for s in habit_stats)
    total_possible = sum(s['total'] for s in habit_stats)
    overall = round((total_completed / total_possible) * 100) if total_possible > 0 else 0

    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; color: #333;">
        <h2 style="color: #2c3e50;">📊 Your Weekly Habit Summary</h2>
        <p style="color: #666;">{start_date} → {end_date}</p>

        <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
            <h3 style="margin: 0; color: #2c3e50;">Overall Completion</h3>
            <p style="font-size: 48px; margin: 10px 0; font-weight: bold; color: #27ae60;">{overall}%</p>
            <p style="color: #666; margin: 0;">{total_completed} out of {total_possible} habits completed</p>
        </div>

        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: #2c3e50; color: white;">
                    <th style="padding: 12px; text-align:left;">Habit</th>
                    <th style="padding: 12px;">Completed</th>
                    <th style="padding: 12px;">Missed</th>
                    <th style="padding: 12px;">Rate</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <br>
        <p style="color: #999; font-size: 13px;">
            Keep going! Consistency is what builds habits, not perfection.
        </p>
    </body>
    </html>
    """

    ses.send_email(
        Source=FROM_EMAIL,
        Destination={'ToAddresses': [to_email]},
        Message={
            'Subject': {'Data': f'Weekly Habit Summary — {start_date} to {end_date}'},
            'Body': {'Html': {'Data': body_html}}
        }
    )
    print(f'Sent weekly summary to {to_email}')