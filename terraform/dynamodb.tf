resource "aws_dynamodb_table" "habit_tracker" {
  name         = "habit-tracker"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"
  range_key    = "sk"

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "recordType"
    type = "S"
  }

  global_secondary_index {
    name            = "recordType-index"
    hash_key        = "recordType"
    projection_type = "ALL"
  }
}
