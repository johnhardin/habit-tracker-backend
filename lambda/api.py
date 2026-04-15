import json
import boto3
from datetime import datetime, timezone
import uuid

dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
table = dynamodb.Table('habit-tracker')

def lambda_handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    path = event.get('rawPath', '')
    
    try:
        if method == 'GET' and path == '/habits':
            return get_habits(event)
        elif method == 'POST' and path == '/habits':
            return add_habit(event)
        elif method == 'DELETE' and path == '/habits':
            return delete_habit(event)
        else:
            return response(404, {'message': 'Not found'})
    except Exception as e:
        print(f'Error: {str(e)}')
        return response(500, {'message': str(e)})

def get_habits(event):
    params = event.get('queryStringParameters') or {}
    user_id = params.get('userId', 'fakhri')
    
    result = table.scan(
        FilterExpression='userId = :uid AND begins_with(sk, :prefix)',
        ExpressionAttributeValues={
            ':uid': user_id,
            ':prefix': 'HABIT#'
        }
    )
    
    habits = result.get('Items', [])
    return response(200, {'habits': habits})

def add_habit(event):
    body = json.loads(event.get('body', '{}'))
    
    user_id = body.get('userId', 'fakhri')
    name = body.get('name')
    email = body.get('email')
    schedule = body.get('schedule', 'daily')
    reminder_time = body.get('reminderTime', None)
    
    if not all([name, email]):
        return response(400, {'message': 'name and email are required'})
    
    habit_id = name.lower().replace(' ', '-') + '-' + str(uuid.uuid4())[:4]
    
    item = {
        'userId': user_id,
        'sk': f'HABIT#{habit_id}',
        'habitId': habit_id,
        'name': name,
        'email': email,
        'schedule': schedule,
        'createdAt': datetime.now(timezone.utc).isoformat()
    }

    if reminder_time:
        item['reminderTime'] = reminder_time

    table.put_item(Item=item)
    
    return response(201, {'message': 'Habit created', 'habitId': habit_id})

def delete_habit(event):
    params = event.get('queryStringParameters') or {}
    user_id = params.get('userId', 'fakhri')
    habit_id = params.get('habitId')
    
    if not habit_id:
        return response(400, {'message': 'habitId is required'})
    
    table.delete_item(
        Key={
            'userId': user_id,
            'sk': f'HABIT#{habit_id}'
        }
    )
    
    return response(200, {'message': 'Habit deleted'})

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(body)
    }