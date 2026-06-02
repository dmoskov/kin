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
#  Set USE_INSTANCE_CONNECT=true and fill in INSTANCE_ID / AZ / REGION.
#  This pushes your SSH key automatically via EC2 Instance Connect so you
#  never need to manage authorized_keys on the server.
#
#  Find your values in the AWS Console → EC2 → Instances, or:
#    aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,Placement.AvailabilityZone,PublicIpAddress]' --output table
#
# ── Plain VPS / non-AWS users ─────────────────────────────────────────────
#
#  Set USE_INSTANCE_CONNECT=false. Make sure your SSH public key is already
#  in ~/.ssh/authorized_keys on the server. INSTANCE_ID / AZ / REGION are
#  ignored.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────
# Copy this file to private/deploy.sh and fill these in.

SERVER_HOST=""                      # e.g. myserver.example.com or an IP address
SERVER_USER="ec2-user"              # ec2-user (Amazon Linux), ubuntu (Ubuntu), etc.
SSH_KEY="$HOME/.ssh/my-key"         # path to your private key (without .pub)
REMOTE_DIR="/home/ec2-user/family-tree"   # where the app lives on the server

USE_INSTANCE_CONNECT=false          # true = AWS EC2 Instance Connect; false = plain SSH
INSTANCE_ID=""                      # AWS only: i-0abc1234... (ignored if USE_INSTANCE_CONNECT=false)
AZ=""                               # AWS only: us-east-1a   (ignored if USE_INSTANCE_CONNECT=false)
REGION=""                           # AWS only: us-east-1    (ignored if USE_INSTANCE_CONNECT=false)

# ── Preflight ─────────────────────────────────────────────────────────────

if [[ -z "$SERVER_HOST" ]]; then
  echo "Error: SERVER_HOST is not set." >&2
  echo "  Copy this file to private/deploy.sh and fill in the Configuration block." >&2
  exit 1
fi

if [[ ! -f "$SSH_KEY" ]]; then
  echo "Error: SSH key not found at $SSH_KEY" >&2
  exit 1
fi

if $USE_INSTANCE_CONNECT && ! command -v aws &>/dev/null; then
  echo "Error: USE_INSTANCE_CONNECT=true but aws CLI not found." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"

# ── Step 1: Auth ──────────────────────────────────────────────────────────

if $USE_INSTANCE_CONNECT; then
  echo "Pushing SSH key via EC2 Instance Connect..."
  aws ec2-instance-connect send-ssh-public-key \
    --region "$REGION" \
    --instance-id "$INSTANCE_ID" \
    --instance-os-user "$SERVER_USER" \
    --ssh-public-key "file://${SSH_KEY}.pub" \
    --availability-zone "$AZ" \
    --no-cli-pager
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
