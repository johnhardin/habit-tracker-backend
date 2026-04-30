resource "aws_cloudwatch_event_rule" "hourly_notify" {
  name                = "habit-tracker-hourly-notify"
  schedule_expression = "cron(0 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "notify" {
  rule      = aws_cloudwatch_event_rule.hourly_notify.name
  target_id = "habit-tracker-notify"
  arn       = aws_lambda_function.notify.arn
}

resource "aws_lambda_permission" "eventbridge_notify" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notify.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.hourly_notify.arn
}

resource "aws_cloudwatch_event_rule" "weekly_summary" {
  name                = "habit-tracker-weekly-summary"
  schedule_expression = "cron(0 22 ? * SUN *)"
}

resource "aws_cloudwatch_event_target" "weekly" {
  rule      = aws_cloudwatch_event_rule.weekly_summary.name
  target_id = "habit-tracker-weekly"
  arn       = aws_lambda_function.weekly.arn
}

resource "aws_lambda_permission" "eventbridge_weekly" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.weekly.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_summary.arn
}
