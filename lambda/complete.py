import json
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
table = dynamodb.Table('habit-tracker')

def lambda_handler(event, context):
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        habit_id = params.get('habitId')
        date = params.get('date')

        if not all([user_id, habit_id, date]):
            return response(400, 'Missing required parameters')

        sk = f'COMPLETION#{date}#{habit_id}'

        table.put_item(Item={
            'userId': user_id,
            'sk': sk,
            'habitId': habit_id,
            'completedAt': datetime.now(timezone.utc).isoformat(),
            'date': date
        })

        return response(200, f'Habit marked as complete. Great job!')

    except Exception as e:
        print(f'Error: {str(e)}')
        return response(500, 'Something went wrong')

def response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'text/html',
        },
        'body': f'<h2>{message}</h2>'
    }