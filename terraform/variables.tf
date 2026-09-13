variable "project_name" {
  description = "Prefix for all resource names"
  type        = string
  default     = "drinkbot"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

# --- Database ---

variable "db_instance_class" {
  type    = string
  default = "db.t4g.small"
}

variable "db_name" {
  type    = string
  default = "drinkbot"
}

variable "db_username" {
  type    = string
  default = "drinkbot"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for production"
  type        = bool
  default     = false
}

# --- Container images (pushed to the ECR repos this config creates) ---

variable "backend_image_tag" {
  type    = string
  default = "latest"
}

variable "frontend_image_tag" {
  type    = string
  default = "latest"
}

# --- ECS sizing ---

variable "backend_cpu" {
  type    = number
  default = 512
}

variable "backend_memory" {
  type    = number
  default = 1024
}

# Keep at 1 while migrations run on task startup; scale out after
# moving `alembic upgrade head` to a dedicated deploy step.
variable "backend_desired_count" {
  type    = number
  default = 1
}

variable "frontend_desired_count" {
  type    = number
  default = 1
}

variable "backend_max_count" {
  description = "Upper bound for backend autoscaling"
  type        = number
  default     = 4
}

# --- LLM (external API — no LLM infrastructure is deployed) ---

variable "llm_provider" {
  description = "LLM API provider: openai or gemini"
  type        = string
  default     = "openai"

  validation {
    condition     = contains(["openai", "gemini"], var.llm_provider)
    error_message = "llm_provider must be openai or gemini."
  }
}

variable "llm_model" {
  description = "Model name for the chosen provider (e.g. gpt-4o-mini, gemini-2.0-flash)"
  type        = string
  default     = "gpt-4o-mini"
}

variable "llm_api_key" {
  description = "API key for the LLM provider (stored in Secrets Manager)"
  type        = string
  sensitive   = true
}
