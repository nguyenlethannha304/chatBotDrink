resource "random_password" "db" {
  length  = 32
  special = false
}

resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "jwt" {
  name_prefix             = "${var.project_name}/jwt-secret-"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "jwt" {
  secret_id     = aws_secretsmanager_secret.jwt.id
  secret_string = random_password.jwt.result
}

resource "aws_secretsmanager_secret" "llm_api_key" {
  name_prefix             = "${var.project_name}/llm-api-key-"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "llm_api_key" {
  secret_id     = aws_secretsmanager_secret.llm_api_key.id
  secret_string = var.llm_api_key
}

# Full async SQLAlchemy URL — the only DB config the app reads
resource "aws_secretsmanager_secret" "database_url" {
  name_prefix             = "${var.project_name}/database-url-"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql+asyncpg://%s:%s@%s/%s",
    var.db_username,
    random_password.db.result,
    aws_db_instance.main.endpoint,
    var.db_name,
  )
}
