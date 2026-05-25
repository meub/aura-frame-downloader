# AWS Deployment Guide

This guide deploys the Aura Frame Downloader as a scheduled **AWS ECS Fargate** task
that backs up your Aura frame photos to S3 on a recurring schedule.

All AWS resources are managed by a single CloudFormation template at
`infrastructure/cloudformation.yaml`.  One deploy command creates everything.

---

## Architecture

```
EventBridge (cron rule)
    └─► ECS Scheduled Task (Fargate)
            ├─ Image: ECR (private repository)
            ├─ Credentials: AWS Secrets Manager (injected at startup)
            └─► S3 Bucket (versioned photo storage)
```

---

## Prerequisites

- AWS CLI configured (`aws configure`)
- Docker with BuildKit (Docker Desktop ≥ 4.x)
- Permissions to create: S3, ECR, ECS, IAM, EventBridge, Secrets Manager, CloudWatch Logs

---

## Step 1 — Find a subnet

The Fargate task needs a public VPC subnet with internet access to reach the Aura API.
A subnet from the default VPC works:

```bash
aws ec2 describe-subnets \
  --filters Name=defaultForAz,Values=true \
  --query 'Subnets[0].SubnetId' \
  --output text
# → subnet-xxxxxxxx
```

---

## Step 2 — Deploy the CloudFormation stack

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yaml \
  --stack-name aura-backup \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      AuraEmail=you@example.com \
      AuraPassword=your-password \
      "AuraFrames=[{\"name\":\"Living Room\",\"frame_id\":\"your-frame-uuid\",\"s3_prefix\":\"living-room\"}]" \
      BucketName=my-aura-backup-YOURNAME \
      SubnetId=subnet-xxxxxxxx \
      CpuArchitecture=X86_64
```

> **Apple Silicon (M1/M2/M3)?** Use `CpuArchitecture=ARM64` — the image and the Fargate
> task must share the same architecture.

Optional parameters and their defaults:

| Parameter | Default | Notes |
|---|---|---|
| `ScheduleExpression` | `cron(0 2 * * ? *)` | Daily at 02:00 UTC |
| `OrganizeByYear` | `false` | Set `true` to group by year sub-folder |
| `CpuArchitecture` | `X86_64` | `ARM64` for Apple Silicon builds |

---

## Step 3 — Build and push the Docker image

```bash
# Get the ECR URI from the stack outputs
ECR_URI=$(aws cloudformation describe-stacks \
  --stack-name aura-backup \
  --query "Stacks[0].Outputs[?OutputKey=='ECRRepositoryUri'].OutputValue" \
  --output text)

# Authenticate Docker to ECR
aws ecr get-login-password \
  | docker login --username AWS --password-stdin "$ECR_URI"

# Build for the correct platform (match CpuArchitecture above)
docker build --platform linux/amd64 -t "$ECR_URI:latest" .
# docker build --platform linux/arm64 -t "$ECR_URI:latest" .  # ← ARM64

# Push
docker push "$ECR_URI:latest"
```

---

## Step 4 — Test a manual run

Trigger the task immediately rather than waiting for the schedule:

```bash
CLUSTER=$(aws cloudformation describe-stacks \
  --stack-name aura-backup \
  --query "Stacks[0].Outputs[?OutputKey=='ClusterName'].OutputValue" \
  --output text)

TASK_DEF=$(aws cloudformation describe-stacks \
  --stack-name aura-backup \
  --query "Stacks[0].Outputs[?OutputKey=='TaskDefinitionArn'].OutputValue" \
  --output text)

aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEF" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxxx],assignPublicIp=ENABLED}"
```

Tail the CloudWatch logs:

```bash
aws logs tail /ecs/aura-backup --follow
```

A successful first run ends with:
```
All frames completed successfully
Frame 'Living Room' complete: downloaded=N skipped=0 total=N
```

A subsequent run shows all photos skipped (S3 existence check working):
```
Frame 'Living Room' complete: downloaded=0 skipped=N total=N
```

---

## Updating the container image

Push a new `:latest` image — no stack re-deploy needed.  The next scheduled run
(or the next manual `aws ecs run-task`) automatically pulls the new image.

```bash
docker build --platform linux/amd64 -t "$ECR_URI:latest" .
docker push "$ECR_URI:latest"
```

---

## Updating stack parameters

To change the schedule, add a frame, or toggle `OrganizeByYear`, re-run
`aws cloudformation deploy` with the updated `--parameter-overrides`.
CloudFormation applies a change-set and only modifies affected resources.

---

## Tearing down

```bash
# Empty the S3 bucket first (CloudFormation won't delete a non-empty bucket)
aws s3 rm s3://my-aura-backup-YOURNAME --recursive

aws cloudformation delete-stack --stack-name aura-backup
```

---

## Cost estimate

For a typical Aura frame (~500–2000 photos, daily backup after the first full run):

| Service | Usage | Est. monthly cost |
|---|---|---|
| ECS Fargate | ~5 min/day, 0.25 vCPU / 0.5 GB | < $0.10 |
| S3 storage | ~10 GB photos | ~$0.23 |
| S3 requests | ~2 000 HEAD + few PUTs/day | < $0.01 |
| Secrets Manager | 1 secret | $0.40 |
| **Total** | | **~$0.75/month** |
