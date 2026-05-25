# AWS Deployment Guide

This guide walks through deploying the Aura Frame Downloader as a scheduled
**AWS ECS Fargate** task that backs up your Aura frame photos to S3 on a
recurring schedule.

---

## Architecture Overview

```
EventBridge (cron rule)
    └─► ECS Scheduled Task (Fargate)
            ├─ Image: ECR (your private repo)
            ├─ Credentials: AWS Secrets Manager
            └─► S3 Bucket (photo storage)
```

---

## Prerequisites

- AWS CLI configured (`aws configure`)
- Docker installed locally
- An AWS account with permissions to create: S3, ECR, ECS, IAM, EventBridge, Secrets Manager

---

## Step 1: Create the S3 Bucket

```bash
aws s3api create-bucket \
  --bucket my-aura-backup \
  --region us-east-1

# Enable versioning (recommended — lets you recover accidentally deleted photos)
aws s3api put-bucket-versioning \
  --bucket my-aura-backup \
  --versioning-configuration Status=Enabled

# Block all public access
aws s3api put-public-access-block \
  --bucket my-aura-backup \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,\
BlockPublicPolicy=true,RestrictPublicBuckets=true
```

---

## Step 2: Store Credentials in AWS Secrets Manager

Never put your Aura password in ECS task environment variables — use Secrets Manager:

```bash
# Store Aura credentials as a single JSON secret
aws secretsmanager create-secret \
  --name aura-frame-downloader/credentials \
  --secret-string '{
    "AURA_EMAIL": "you@example.com",
    "AURA_PASSWORD": "your-aura-password"
  }'

# Note the ARN returned — you'll need it in the task definition
```

---

## Step 3: Create an ECR Repository and Push the Image

```bash
# Create the repository
aws ecr create-repository --repository-name aura-frame-downloader

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS \
    --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build, tag, and push
docker build -t aura-frame-downloader .
docker tag aura-frame-downloader:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frame-downloader:latest
docker push \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frame-downloader:latest
```

---

## Step 4: Create the IAM Task Role

The ECS task needs permission to read the secret and write to S3.

```bash
# Create the role
aws iam create-role \
  --role-name AuraFrameDownloaderTaskRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# S3 write policy
aws iam put-role-policy \
  --role-name AuraFrameDownloaderTaskRole \
  --policy-name S3WritePolicy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:HeadObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::my-aura-backup/*"
    }, {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::my-aura-backup"
    }]
  }'

# Secrets Manager read policy
aws iam put-role-policy \
  --role-name AuraFrameDownloaderTaskRole \
  --policy-name SecretsManagerReadPolicy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:aura-frame-downloader/credentials-*"
    }]
  }'
```

You also need a separate **Task Execution Role** (for ECS to pull the image and inject secrets):

```bash
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Add permission to read the secret during container startup
aws iam put-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-name SecretsManagerForECS \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:aura-frame-downloader/credentials-*"
    }]
  }'
```

---

## Step 5: Register the ECS Task Definition

Create `task-definition.json` (replace ARNs and frame IDs with your values):

```json
{
  "family": "aura-frame-downloader",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "taskRoleArn": "arn:aws:iam::123456789012:role/AuraFrameDownloaderTaskRole",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "containerDefinitions": [{
    "name": "aura-backup",
    "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frame-downloader:latest",
    "essential": true,
    "environment": [
      {
        "name": "S3_BUCKET",
        "value": "my-aura-backup"
      },
      {
        "name": "AWS_DEFAULT_REGION",
        "value": "us-east-1"
      },
      {
        "name": "ORGANIZE_BY_YEAR",
        "value": "true"
      },
      {
        "name": "AURA_FRAMES",
        "value": "[{\"name\":\"Living Room\",\"frame_id\":\"your-frame-uuid\",\"s3_prefix\":\"living-room\"}]"
      }
    ],
    "secrets": [
      {
        "name": "AURA_EMAIL",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:aura-frame-downloader/credentials:AURA_EMAIL::"
      },
      {
        "name": "AURA_PASSWORD",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:aura-frame-downloader/credentials:AURA_PASSWORD::"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/aura-frame-downloader",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
```

```bash
# Create the CloudWatch log group first
aws logs create-log-group --log-group-name /ecs/aura-frame-downloader

# Register the task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

---

## Step 6: Create the ECS Cluster

```bash
aws ecs create-cluster --cluster-name aura-backup-cluster
```

---

## Step 7: Create the EventBridge Scheduled Rule

This triggers the ECS task on a schedule (example: daily at 2 AM UTC).

```bash
# Create the schedule rule
aws events put-rule \
  --name aura-daily-backup \
  --schedule-expression "cron(0 2 * * ? *)" \
  --state ENABLED \
  --description "Daily Aura frame photo backup to S3"

# Grant EventBridge permission to run ECS tasks
aws iam create-role \
  --role-name EventBridgeECSRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "events.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam put-role-policy \
  --role-name EventBridgeECSRole \
  --policy-name RunECSTask \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "ecs:RunTask",
      "Resource": "arn:aws:ecs:us-east-1:123456789012:task-definition/aura-frame-downloader:*"
    }, {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::123456789012:role/AuraFrameDownloaderTaskRole",
        "arn:aws:iam::123456789012:role/ecsTaskExecutionRole"
      ]
    }]
  }'

# Add the ECS task as the rule target (replace subnet/sg IDs with yours)
aws events put-targets \
  --rule aura-daily-backup \
  --targets '[{
    "Id": "1",
    "Arn": "arn:aws:ecs:us-east-1:123456789012:cluster/aura-backup-cluster",
    "RoleArn": "arn:aws:iam::123456789012:role/EventBridgeECSRole",
    "EcsParameters": {
      "TaskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/aura-frame-downloader",
      "TaskCount": 1,
      "LaunchType": "FARGATE",
      "NetworkConfiguration": {
        "awsvpcConfiguration": {
          "Subnets": ["subnet-xxxxxxxx"],
          "AssignPublicIp": "ENABLED"
        }
      }
    }
  }]'
```

---

## Step 8: Test a Manual Run

Trigger a one-off task run to verify everything works before the schedule fires:

```bash
aws ecs run-task \
  --cluster aura-backup-cluster \
  --task-definition aura-frame-downloader \
  --launch-type FARGATE \
  --network-configuration 'awsvpcConfiguration={
    subnets=[subnet-xxxxxxxx],
    assignPublicIp=ENABLED
  }'
```

Then tail the CloudWatch logs:

```bash
aws logs tail /ecs/aura-frame-downloader --follow
```

Look for lines like:
```
Frame 'Living Room' complete: downloaded=42 skipped=0 total=42
All frames completed successfully
```

On the second run you should see `skipped=42`.

---

## Updating the Container Image

```bash
docker build -t aura-frame-downloader .
docker tag aura-frame-downloader:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frame-downloader:latest
docker push \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-frame-downloader:latest

# Register a new task definition revision
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

EventBridge will pick up the latest task definition revision on the next scheduled run.

---

## Cost Estimate

For a daily backup of a typical Aura frame (~500–2000 photos total after the first run):

| Service | Usage | Est. monthly cost |
|---|---|---|
| ECS Fargate | ~5 min/day, 0.25 vCPU / 0.5 GB | < $0.10 |
| S3 storage | ~10 GB photos | ~$0.23 |
| S3 requests | ~2000 HEAD + few PUTs/day | < $0.01 |
| Secrets Manager | 1 secret | $0.40 |
| **Total** | | **~$0.75/month** |
