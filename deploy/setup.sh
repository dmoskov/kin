#!/bin/bash
# EC2 setup script for the Family Tree web server.
# Run as: sudo bash setup.sh
#
# Prerequisites:
#   - Amazon Linux 2023 or similar
#   - RDS PostgreSQL instance already running
#   - .env file created at /home/ec2-user/family-tree/.env with DATABASE_URL
#     (passwordless DSN + RDS IAM auth — see README "Database authentication")

set -euo pipefail

echo "=== Installing system packages ==="
dnf install -y python3.11 python3.11-pip nginx git postgresql16

echo "=== Setting up application ==="
cd /home/ec2-user/family-tree
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Initializing database ==="
cd src
python -c "from database.connection import init_db; print(init_db())"

echo "=== Configuring nginx ==="
cp /home/ec2-user/family-tree/deploy/nginx.conf /etc/nginx/conf.d/familytree.conf
# Remove default server block if present
rm -f /etc/nginx/conf.d/default.conf
nginx -t
systemctl enable nginx
systemctl restart nginx

echo "=== Creating the familytree service user ==="
# The app runs as a no-login system user with no sudo; ec2-user stays the
# deploy user and owns the code. The app only reads the code and only writes
# private/documents (uploads). .env is read by systemd as root.
id familytree &>/dev/null || useradd --system --user-group --no-create-home \
  --home-dir /var/lib/familytree --shell /sbin/nologin familytree
setfacl -m u:familytree:x /home/ec2-user
mkdir -p /home/ec2-user/family-tree/private/documents
chown ec2-user:ec2-user /home/ec2-user/family-tree/private/documents
setfacl -R -m u:familytree:rwX,d:u:familytree:rwX,d:u:ec2-user:rwX \
  /home/ec2-user/family-tree/private/documents
chmod 600 /home/ec2-user/family-tree/.env

echo "=== Configuring systemd service ==="
cp /home/ec2-user/family-tree/deploy/familytree.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable familytree
systemctl restart familytree

echo "=== Configuring nightly database backup ==="
# pg_dump → S3 every night. Requires BACKUP_S3_BUCKET (or S3_BUCKET) in the
# .env file. Restore instructions: deploy/BACKUPS.md
cp /home/ec2-user/family-tree/deploy/familytree-backup.service /etc/systemd/system/
cp /home/ec2-user/family-tree/deploy/familytree-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now familytree-backup.timer

echo ""
echo "=== Done! ==="
echo "  App: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "  API: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/api/data"
echo ""
echo "  Logs: journalctl -u familytree -f"
