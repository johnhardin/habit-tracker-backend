data "archive_file" "api" {
  type        = "zip"
  source_file = "${path.module}/../lambda/api.py"
  output_path = "${path.module}/../lambda/api.zip"
}

data "archive_file" "complete" {
  type        = "zip"
  source_file = "${path.module}/../lambda/complete.py"
  output_path = "${path.module}/../lambda/complete.zip"
}

data "archive_file" "notify" {
  type        = "zip"
  source_file = "${path.module}/../lambda/notify.py"
  output_path = "${path.module}/../lambda/notify.zip"
}

data "archive_file" "weekly" {
  type        = "zip"
  source_file = "${path.module}/../lambda/weekly.py"
  output_path = "${path.module}/../lambda/weekly.zip"
}

resource "aws_lambda_function" "api" {
  filename         = data.archive_file.api.output_path
  function_name    = "habit-tracker-api"
  role             = aws_iam_role.lambda_role.arn
  handler          = "api.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.api.output_base64sha256
}

resource "aws_lambda_function" "complete" {
  filename         = data.archive_file.complete.output_path
  function_name    = "habit-tracker-complete"
  role             = aws_iam_role.lambda_role.arn
  handler          = "complete.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.complete.output_base64sha256
}

resource "aws_lambda_function" "notify" {
  filename         = data.archive_file.notify.output_path
  function_name    = "habit-tracker-notify"
  role             = aws_iam_role.lambda_role.arn
  handler          = "notify.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.notify.output_base64sha256

  environment {
    variables = {
      API_BASE_URL = aws_apigatewayv2_stage.default.invoke_url
    }
  }
}

resource "aws_lambda_function" "weekly" {
  filename         = data.archive_file.weekly.output_path
  function_name    = "habit-tracker-weekly"
  role             = aws_iam_role.lambda_role.arn
  handler          = "weekly.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.weekly.output_base64sha256
}
