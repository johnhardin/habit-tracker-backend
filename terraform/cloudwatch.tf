resource "aws_sns_topic" "alerts" {
  name = "habit-tracker-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "chocobibi.ff@gmail.com"
}

# Lambda error alarms

resource "aws_cloudwatch_metric_alarm" "lambda_errors_api" {
  alarm_name          = "habit-tracker-api-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.api.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  alarm_description   = "habit-tracker-api lambda is throwing errors"
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors_complete" {
  alarm_name          = "habit-tracker-complete-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.complete.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  alarm_description   = "habit-tracker-complete lambda is throwing errors"
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors_notify" {
  alarm_name          = "habit-tracker-notify-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.notify.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  alarm_description   = "habit-tracker-notify lambda is throwing errors"
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors_weekly" {
  alarm_name          = "habit-tracker-weekly-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.weekly.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  alarm_description   = "habit-tracker-weekly lambda is throwing errors"
}

# API Gateway 5xx alarm

resource "aws_cloudwatch_metric_alarm" "apigw_5xx" {
  alarm_name          = "habit-tracker-apigw-5xx"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions = {
    ApiId = aws_apigatewayv2_api.main.id
    Stage = "$default"
  }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  alarm_description   = "API Gateway is returning 5xx errors"
}
