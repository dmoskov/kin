#!/usr/bin/env bash
# Deploy web/ and src/ to production EC2 instance.
#
# Usage:  ./deploy/deploy.sh
#
# Requires:
#   - AWS CLI with ec2-instance-connect permissions
#   - SSH key at ~/.ssh/<YOUR_KEY> (+ .pub)
#   - rsync installed locally

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────
EC2_HOST="<YOUR_EC2_HOST>"
EC2_USER="ec2-user"
INSTANCE_ID="<YOUR_INSTANCE_ID>"
AZ="<YOUR_AZ>"
REGION="<YOUR_REGION>"
SSH_KEY="$HOME/.ssh/<YOUR_KEY>"
REMOTE_DIR="/home/ec2-user/family-tree"

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$SCRIPT_DIR/web"
SRC_DIR="$SCRIPT_DIR/src"
PRIVATE_DIR="$SCRIPT_DIR/private"

# ── Preflight checks ──────────────────────────────────────────────────
if [[ ! -f "$SSH_KEY" ]]; then
  echo "Error: SSH key not found at $SSH_KEY" >&2
  exit 1
fi

if ! command -v aws &>/dev/null; then
  echo "Error: aws CLI not found" >&2
  exit 1
fi

echo "=== Deploying to $EC2_USER@$EC2_HOST ==="

# ── Step 1: Push public key via EC2 Instance Connect ──────────────────
echo "Pushing SSH key via EC2 Instance Connect..."
aws ec2-instance-connect send-ssh-public-key \
  --region "$REGION" \
  --instance-id "$INSTANCE_ID" \
  --instance-os-user "$EC2_USER" \
  --ssh-public-key "file://${SSH_KEY}.pub" \
  --availability-zone "$AZ" \
  --no-cli-pager

SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"

# ── Step 2: Ensure remote directories exist ───────────────────────────
echo "Creating remote directories..."
$SSH_CMD "$EC2_USER@$EC2_HOST" \
  "mkdir -p $REMOTE_DIR/private/config $REMOTE_DIR/private/photos"

# ── Step 3: Build the production JS bundle, then rsync app code ────────
echo "Building JS bundle..."
bash "$SCRIPT_DIR/scripts/build_js.sh"

echo "Syncing web/ directory..."
rsync -avz --delete \
  -e "$SSH_CMD" \
  "$WEB_DIR/" \
  "$EC2_USER@$EC2_HOST:$REMOTE_DIR/web/"

echo "Syncing src/ directory..."
rsync -avz --delete --exclude='__pycache__' --exclude='*.egg-info' \
  -e "$SSH_CMD" \
  "$SRC_DIR/" \
  "$EC2_USER@$EC2_HOST:$REMOTE_DIR/src/"

# ── Step 4: rsync private content (config + photos) ──────────────────
if [[ -d "$PRIVATE_DIR" ]]; then
  if [[ -f "$PRIVATE_DIR/config/family-config.json" ]]; then
    echo "Syncing private config..."
    rsync -avz \
      -e "$SSH_CMD" \
      "$PRIVATE_DIR/config/family-config.json" \
      "$EC2_USER@$EC2_HOST:$REMOTE_DIR/private/config/"
  fi

  if [[ -d "$PRIVATE_DIR/photos" ]] && ls "$PRIVATE_DIR/photos/"* &>/dev/null; then
    echo "Syncing private photos..."
    # NOTE: No --delete here! Photos uploaded via the web UI live only on the
    # server; wiping them on deploy would lose user-uploaded content.
    rsync -avz \
      -e "$SSH_CMD" \
      "$PRIVATE_DIR/photos/" \
      "$EC2_USER@$EC2_HOST:$REMOTE_DIR/private/photos/"
  fi
else
  echo "  (no private/ directory — skipping config & photos)"
fi

# ── Step 5: Sync requirements.txt + install Python dependencies ───────
echo "Syncing requirements.txt..."
rsync -avz \
  -e "$SSH_CMD" \
  "$SCRIPT_DIR/requirements.txt" \
  "$EC2_USER@$EC2_HOST:$REMOTE_DIR/requirements.txt"

echo "Installing Python dependencies..."
$SSH_CMD "$EC2_USER@$EC2_HOST" \
  "cd $REMOTE_DIR && ./venv/bin/pip install -q -r requirements.txt"

# ── Step 6: Restart gunicorn ──────────────────────────────────────────
echo "Restarting familytree service..."
$SSH_CMD "$EC2_USER@$EC2_HOST" \
  "sudo systemctl restart familytree"

echo ""
echo "=== Deploy complete ==="
