#!/bin/bash
# EC2 User Data — runs once, automatically, when the instance first boots.
# Paste this into "Advanced details → User data" when launching the EC2
# (or attach via Launch Template). Target: Amazon Linux 2023.
#
# It installs Python, pulls our app code, sets env vars, and starts gunicorn
# on port 5000 as a systemd service so it auto-restarts on crash.
set -eux

# --- 1. Install runtime ---
dnf update -y
dnf install -y python3.11 python3.11-pip git

# --- 2. Fetch app code ---
# Option A: clone from your GitHub repo (recommended — edit the URL):
#   git clone https://github.com/<YOUR_USER>/<YOUR_REPO>.git /opt/clinic
# Option B: for demo, copy the 'app' folder to S3 and pull it down:
#   aws s3 cp s3://<your-bucket>/app /opt/clinic --recursive
mkdir -p /opt/clinic
# <<< REPLACE THIS BLOCK with your git clone or s3 cp command >>>

# --- 3. Python deps ---
cd /opt/clinic
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt

# --- 4. Env vars (DB connection). The RDS endpoint comes from Parameter Store
# in a real setup, but for an assignment, you can hard-code it here after
# RDS is created. NEVER commit real passwords to git.
cat > /etc/clinic.env <<'EOF'
DB_HOST=clinic-db.XXXXX.ap-southeast-1.rds.amazonaws.com
DB_USER=admin
DB_PASS=ChangeMe_StrongPassword
DB_NAME=clinic
EOF
chmod 600 /etc/clinic.env

# --- 5. systemd service — auto-restart on crash, starts on boot ---
cat > /etc/systemd/system/clinic.service <<'EOF'
[Unit]
Description=Clinic Flask app
After=network.target

[Service]
WorkingDirectory=/opt/clinic
EnvironmentFile=/etc/clinic.env
ExecStart=/opt/clinic/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 "app:create_app()"
Restart=always
RestartSec=3
User=ec2-user

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now clinic.service
