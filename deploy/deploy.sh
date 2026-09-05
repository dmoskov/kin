#!/usr/bin/env bash
# Deploy web/ and src/ to a Linux server running the family tree app.
#
# Usage:  bash deploy/deploy.sh
#
# ── Quick setup ───────────────────────────────────────────────────────────
#
#  1. Copy this file somewhere private and fill in the configuration below:
#       cp deploy/deploy.sh private/deploy.sh
#
#  2. Fill in the five variables in the Configuration block.
#
#  3. Run:  bash private/deploy.sh
#
# ── AWS EC2 users ─────────────────────────────────────────────────────────
#
#  Set USE_SSM=true and fill in INSTANCE_ID / REGION. SSH is tunnelled through
#  AWS Systems Manager Session Manager, so the instance needs NO inbound port
#  22 and no public IP. Requires the AWS CLI plus the Session Manager plugin
#  (https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
#  and an identity allowed ssm:StartSession on the instance. Your public key
#  must still be in ~/.ssh/authorized_keys on the server (the familytree-ec2
#  key pair is).
#
#  Find your instance id in the AWS Console → EC2 → Instances, or:
#    aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,Tags[?Key==`Name`]|[0].Value]' --output table
#
# ── Plain VPS / non-AWS users ─────────────────────────────────────────────
#
#  Set USE_SSM=false and put the host/IP in SERVER_HOST. Make sure your SSH
#  public key is already in ~/.ssh/authorized_keys on the server. INSTANCE_ID
#  / REGION are ignored.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────
# Copy this file to private/deploy.sh and fill these in.

SERVER_HOST=""                      # non-AWS only: myserver.example.com or an IP (ignored if USE_SSM=true)
SERVER_USER="ec2-user"              # ec2-user (Amazon Linux), ubuntu (Ubuntu), etc.
SSH_KEY="$HOME/.ssh/my-key"         # path to your private key (without .pub)
REMOTE_DIR="/home/ec2-user/family-tree"   # where the app lives on the server

USE_SSM=false                       # true = SSH over AWS SSM Session Manager (no open port 22); false = plain SSH
INSTANCE_ID=""                      # AWS only: i-0abc1234... (ignored if USE_SSM=false)
REGION=""                           # AWS only: us-east-1    (ignored if USE_SSM=false)

# ── Preflight ─────────────────────────────────────────────────────────────

if $USE_SSM; then
  if [[ -z "$INSTANCE_ID" || -z "$REGION" ]]; then
    echo "Error: USE_SSM=true requires INSTANCE_ID and REGION." >&2
    exit 1
  fi
  if ! command -v aws &>/dev/null || ! command -v session-manager-plugin &>/dev/null; then
    echo "Error: USE_SSM=true needs the aws CLI and the Session Manager plugin." >&2
    exit 1
  fi
  # ssh sees the instance id as the hostname; SSM carries the TCP stream.
  SERVER_HOST="$INSTANCE_ID"
elif [[ -z "$SERVER_HOST" ]]; then
  echo "Error: SERVER_HOST is not set." >&2
  echo "  Copy this file to private/deploy.sh and fill in the Configuration block." >&2
  exit 1
fi

if [[ ! -f "$SSH_KEY" ]]; then
  echo "Error: SSH key not found at $SSH_KEY" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"

# ── Step 1: Transport ─────────────────────────────────────────────────────

if $USE_SSM; then
  echo "SSH will be tunnelled over SSM Session Manager (no inbound port 22)."
  SSH_CMD="$SSH_CMD -o ProxyCommand='aws ssm start-session --region $REGION --target %h --document-name AWS-StartSSHSession --parameters portNumber=%p'"
fi

echo "=== Deploying to $SERVER_USER@$SERVER_HOST ==="

# ── Step 2: Ensure remote directories exist ───────────────────────────────
$SSH_CMD "$SERVER_USER@$SERVER_HOST" \
  "mkdir -p $REMOTE_DIR/private/config $REMOTE_DIR/private/photos"

# ── Step 3: Build the JS bundle, then rsync app code ──────────────────────
echo "Building JS bundle..."
bash "$SCRIPT_DIR/scripts/build_js.sh"

echo "Syncing web/..."
rsync -avz --delete \
  -e "$SSH_CMD" \
  "$SCRIPT_DIR/web/" \
  "$SERVER_USER@$SERVER_HOST:$REMOTE_DIR/web/"

echo "Syncing src/..."
rsync -avz --delete --exclude='__pycache__' --exclude='*.egg-info' \
  -e "$SSH_CMD" \
  "$SCRIPT_DIR/src/" \
  "$SERVER_USER@$SERVER_HOST:$REMOTE_DIR/src/"

# ── Step 4: Sync private config + photos (if present locally) ────────────
PRIVATE_DIR="$SCRIPT_DIR/private"
if [[ -f "$PRIVATE_DIR/config/family-config.json" ]]; then
  echo "Syncing private/config/family-config.json..."
  rsync -avz \
    -e "$SSH_CMD" \
    "$PRIVATE_DIR/config/family-config.json" \
    "$SERVER_USER@$SERVER_HOST:$REMOTE_DIR/private/config/"
fi

if [[ -d "$PRIVATE_DIR/photos" ]] && compgen -G "$PRIVATE_DIR/photos/*" &>/dev/null; then
  echo "Syncing private/photos/ (additive — no --delete)..."
  rsync -avz \
    -e "$SSH_CMD" \
    "$PRIVATE_DIR/photos/" \
    "$SERVER_USER@$SERVER_HOST:$REMOTE_DIR/private/photos/"
fi

# ── Step 5: Install Python dependencies ──────────────────────────────────
echo "Syncing requirements.txt and installing dependencies..."
rsync -avz \
  -e "$SSH_CMD" \
  "$SCRIPT_DIR/requirements.txt" \
  "$SERVER_USER@$SERVER_HOST:$REMOTE_DIR/requirements.txt"

$SSH_CMD "$SERVER_USER@$SERVER_HOST" \
  "cd $REMOTE_DIR && ./venv/bin/pip install -q -r requirements.txt"

# ── Step 6: Restart the app ───────────────────────────────────────────────
echo "Restarting familytree service..."
$SSH_CMD "$SERVER_USER@$SERVER_HOST" \
  "sudo systemctl restart familytree"

echo ""
echo "=== Deploy complete ==="
