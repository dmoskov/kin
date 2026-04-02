#!/bin/bash
# EC2 setup script for the Family Tree web server.
# Run as: sudo bash setup.sh
#
# Prerequisites:
#   - Amazon Linux 2023 or similar
#   - RDS PostgreSQL instance already running
#   - .env file created at /home/ec2-user/family-tree/.env with DATABASE_URL

set -euo pipefail

echo "=== Installing system packages ==="
dnf install -y python3.11 python3.11-pip nginx git

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

echo "=== Configuring systemd service ==="
cp /home/ec2-user/family-tree/deploy/familytree.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable familytree
systemctl restart familytree

echo ""
echo "=== Done! ==="
echo "  App: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "  API: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/api/data"
echo ""
echo "  Logs: journalctl -u familytree -f"
