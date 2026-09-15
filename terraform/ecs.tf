resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# --- Security groups ---

resource "aws_security_group" "backend" {
  name_prefix = "${var.project_name}-backend-"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "API from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "frontend" {
  name_prefix = "${var.project_name}-frontend-"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTP from ALB"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# --- IAM ---

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.project_name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "read-app-secrets"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.jwt.arn,
        aws_secretsmanager_secret.database_url.arn,
        aws_secretsmanager_secret.llm_api_key.arn,
      ]
    }]
  })
}

resource "aws_iam_role" "task" {
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

# --- Logs ---

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}-backend"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.project_name}-frontend"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_metric_filter" "llm_errors" {
  name           = "${var.project_name}-llm-errors"
  log_group_name = aws_cloudwatch_log_group.backend.name
  pattern        = "{ $.event = \"llm_invocation\" && $.success = false }"

  metric_transformation {
    name      = "LLMInvocationErrors"
    namespace = "${var.project_name}/LLM"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "llm_slow_calls" {
  name           = "${var.project_name}-llm-slow-calls"
  log_group_name = aws_cloudwatch_log_group.backend.name
  pattern        = "{ $.event = \"llm_invocation\" && $.latency_ms > 5000 }"

  metric_transformation {
    name      = "LLMSlowCalls"
    namespace = "${var.project_name}/LLM"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "llm_errors" {
  alarm_name          = "${var.project_name}-llm-errors"
  alarm_description   = "LLM invocation failures exceed the deployment safety threshold"
  namespace           = "${var.project_name}/LLM"
  metric_name         = "LLMInvocationErrors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "llm_slow_calls" {
  alarm_name          = "${var.project_name}-llm-slow-calls"
  alarm_description   = "LLM calls slower than five seconds exceed the threshold"
  namespace           = "${var.project_name}/LLM"
  metric_name         = "LLMSlowCalls"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
}

# --- Backend service ---

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
    essential = true

    portMappings = [{ containerPort = 8000, protocol = "tcp" }]

    # Migrations + seed on startup keeps parity with docker-compose;
    # move to a one-off deploy task before scaling beyond 1 task.
    command = [
      "sh", "-c",
      "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    ]

    environment = [
      { name = "LLM_PROVIDER", value = var.llm_provider },
      # Both are set from llm_model; only the active provider's is read
      { name = "OPENAI_MODEL", value = var.llm_model },
      { name = "GEMINI_MODEL", value = var.llm_model },
      { name = "LLM_INPUT_COST_PER_MILLION", value = "0.15" },
      { name = "LLM_OUTPUT_COST_PER_MILLION", value = "0.60" },
      { name = "CORS_ORIGINS", value = "http://${aws_lb.main.dns_name}" },
    ]

    secrets = [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
      { name = "JWT_SECRET", valueFrom = aws_secretsmanager_secret.jwt.arn },
      { name = upper("${var.llm_provider}_API_KEY"), valueFrom = aws_secretsmanager_secret.llm_api_key.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.backend.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "backend"
      }
    }
  }])
}

resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.backend.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  # LLM responses are slow; give tasks time to drain
  health_check_grace_period_seconds = 120

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener_rule.api]
}

# --- Frontend service ---

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "${aws_ecr_repository.frontend.repository_url}:${var.frontend_image_tag}"
    essential = true

    portMappings = [{ containerPort = 80, protocol = "tcp" }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.frontend.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "frontend"
      }
    }
  }])
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.project_name}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.frontend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.frontend.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }

  depends_on = [aws_lb_listener.http]
}

# --- Backend autoscaling (CPU-based) ---

resource "aws_appautoscaling_target" "backend" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = var.backend_desired_count
  max_capacity       = var.backend_max_count
}

resource "aws_appautoscaling_policy" "backend_cpu" {
  name               = "${var.project_name}-backend-cpu"
  service_namespace  = aws_appautoscaling_target.backend.service_namespace
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  policy_type        = "TargetTrackingScaling"

  target_tracking_scaling_policy_configuration {
    target_value = 70

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
