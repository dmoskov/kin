#!/usr/bin/env bash
# One-time AWS setup so GitHub Actions can deploy familytree-web WITHOUT SSH.
#
# Run once with an admin identity (a read-mostly operator role cannot write IAM):
#   INSTANCE_ID=i-... DEPLOY_BUCKET=<bucket> bash deploy/aws-ssm-deploy-setup.sh
# INSTANCE_ID is the web host; DEPLOY_BUCKET is the private artifact bucket the
# workflow uploads to (both also stored as GitHub Actions repository variables
# DEPLOY_INSTANCE_ID / DEPLOY_BUCKET). Nothing account-specific is hardcoded here.
#
# What it does (all idempotent):
#   1. Lets the instance role register with SSM (AmazonSSMManagedInstanceCore)
#      and read deploy artifacts from the private deploy bucket.
#   2. Creates the GitHub OIDC role `github-actions-kin-deploy`, trusted ONLY
#      for dmoskov/kin refs/heads/main, allowed to upload one artifact and run
#      AWS-RunShellScript on the single web instance.
# The bucket itself (private, SSE-S3, 30-day expiry) is created separately and
# is not recreated here.
set -euo pipefail

: "${INSTANCE_ID:?set INSTANCE_ID to the EC2 instance id of the web host}"
: "${DEPLOY_BUCKET:?set DEPLOY_BUCKET to the private deploy artifact bucket}"
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
INSTANCE_ROLE="${INSTANCE_ROLE:-familytree-ec2-role}"
BUCKET="$DEPLOY_BUCKET"
DEPLOY_ROLE="${DEPLOY_ROLE:-github-actions-kin-deploy}"
REPO="${REPO:-dmoskov/kin}"

echo "== instance role: SSM + artifact read"
aws iam attach-role-policy --role-name "$INSTANCE_ROLE" \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam put-role-policy --role-name "$INSTANCE_ROLE" --policy-name familytree-deploy-artifacts \
  --policy-document "$(cat <<JSON
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":"s3:GetObject","Resource":"arn:aws:s3:::${BUCKET}/*"},
 {"Effect":"Allow","Action":"s3:ListBucket","Resource":"arn:aws:s3:::${BUCKET}"}]}
JSON
)"

echo "== GitHub Actions deploy role"
TRUST="$(cat <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
 "Principal":{"Federated":"arn:aws:iam::${ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"},
 "Action":"sts:AssumeRoleWithWebIdentity",
 "Condition":{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com"},
              "StringLike":{"token.actions.githubusercontent.com:sub":"repo:${REPO}:ref:refs/heads/main"}}}]}
JSON
)"
if aws iam get-role --role-name "$DEPLOY_ROLE" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$DEPLOY_ROLE" --policy-document "$TRUST"
else
  aws iam create-role --role-name "$DEPLOY_ROLE" \
    --description "GitHub Actions deploy for ${REPO} (family-tree) via SSM, no SSH" \
    --tags Key=Project,Value=family-tree \
    --assume-role-policy-document "$TRUST" >/dev/null
fi
aws iam put-role-policy --role-name "$DEPLOY_ROLE" --policy-name kin-deploy-via-ssm \
  --policy-document "$(cat <<JSON
{"Version":"2012-10-17","Statement":[
 {"Sid":"UploadArtifact","Effect":"Allow","Action":"s3:PutObject","Resource":"arn:aws:s3:::${BUCKET}/*"},
 {"Sid":"RunShellOnWebHost","Effect":"Allow","Action":"ssm:SendCommand",
  "Resource":["arn:aws:ssm:${REGION}::document/AWS-RunShellScript",
              "arn:aws:ec2:${REGION}:${ACCOUNT}:instance/${INSTANCE_ID}"]},
 {"Sid":"ReadCommandResult","Effect":"Allow",
  "Action":["ssm:GetCommandInvocation","ssm:ListCommandInvocations"],"Resource":"*"}]}
JSON
)"
echo "done: arn:aws:iam::${ACCOUNT}:role/${DEPLOY_ROLE}"
echo "next: wait ~1 min, then check:  aws ssm describe-instance-information --region ${REGION}"
