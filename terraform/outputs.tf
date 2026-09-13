output "app_url" {
  description = "Public URL of the application"
  value       = "http://${aws_lb.main.dns_name}"
}

output "api_docs_url" {
  value = "http://${aws_lb.main.dns_name}/docs"
}

output "ecr_backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  value = aws_db_instance.main.endpoint
}
