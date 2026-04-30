variable "aws_region" {
  description = "AWS region to deploy resources"
  default     = "ap-southeast-1"
}

variable "from_email" {
  description = "SES-verified email address used to send reminders and summaries"
  default     = "noreply@johnhardin.site"
}
