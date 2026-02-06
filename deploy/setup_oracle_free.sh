#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# LoopCanvas — Oracle Cloud Free Tier Setup
#
# Oracle Cloud Always Free:
#   - 4 OCPU ARM (Ampere A1) — 24GB RAM
#   - 200GB block storage
#   - 10TB outbound data/month
#   - FOREVER FREE. Not a trial. Not credits. Free.
#
# This script sets up a fresh Oracle Cloud ARM VM to run
# the LoopCanvas generation server 24/7.
#
# Prerequisites:
#   1. Oracle Cloud account (free): cloud.oracle.com
#   2. Create an "Always Free" ARM compute instance:
#      - Shape: VM.Standard.A1.Flex (4 OCPU, 24GB RAM)
#      - Image: Ubuntu 22.04 (Canonical)
#      - Add SSH key
#   3. SSH into the instance and run this script
# ═══════════════════════════════════════════════════════════════

set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║    LoopCanvas — Oracle Cloud Free Tier Setup         ║"
echo "╚══════════════════════════════════════════════════════╝"

# System updates
echo "[1/8] Updating system..."
sudo apt update && sudo apt upgrade -y

# Python 3.11
echo "[2/8] Installing Python 3.11..."
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# FFmpeg
echo "[3/8] Installing FFmpeg..."
sudo apt install -y ffmpeg

# System dependencies for librosa/audio
echo "[4/8] Installing audio dependencies..."
sudo apt install -y libsndfile1 libsndfile1-dev

# Create app directory
echo "[5/8] Setting up application..."
mkdir -p ~/loopcanvas
cd ~/loopcanvas

# Clone repo (replace with your repo URL)
# git clone https://github.com/YOUR_USERNAME/loopcanvas.git .
echo "NOTE: Clone your repo here or scp your files"

# Python environment
echo "[6/8] Creating Python environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies (no GPU packages — ARM CPU only)
pip install --upgrade pip
pip install \
    torch --index-url https://download.pytorch.org/whl/cpu \
    diffusers transformers accelerate \
    pillow librosa numpy scipy tqdm \
    soundfile

# Create systemd service for 24/7 operation
echo "[7/8] Creating systemd service..."
sudo tee /etc/systemd/system/loopcanvas.service > /dev/null << 'SYSTEMD'
[Unit]
Description=LoopCanvas Generation Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/loopcanvas/loopcanvas_app
Environment="LOOPCANVAS_MODE=fast"
Environment="PATH=/home/ubuntu/loopcanvas/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/home/ubuntu/loopcanvas/venv/bin/python3 server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Resource limits
LimitNOFILE=65536
MemoryMax=20G

[Install]
WantedBy=multi-user.target
SYSTEMD

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable loopcanvas
sudo systemctl start loopcanvas

# Open firewall port
echo "[8/8] Opening port 8888..."
sudo iptables -I INPUT -p tcp --dport 8888 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT

# Also update Oracle Cloud security list:
echo ""
echo "═══════════════════════════════════════════════════════"
echo "IMPORTANT: Also open port 8888 in Oracle Cloud Console:"
echo "  Networking → Virtual Cloud Networks → Security Lists"
echo "  → Add Ingress Rule: Source 0.0.0.0/0, TCP, Port 8888"
echo "═══════════════════════════════════════════════════════"
echo ""

# Nginx reverse proxy (optional, for port 80)
sudo apt install -y nginx
sudo tee /etc/nginx/sites-available/loopcanvas > /dev/null << 'NGINX'
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/loopcanvas /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║              Setup Complete!                          ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Server: http://$(curl -s ifconfig.me):8888           ║"
echo "║  Mode:   fast (SDXL + Ken Burns, CPU)                ║"
echo "║  Cost:   \$0/month forever                            ║"
echo "║                                                       ║"
echo "║  Commands:                                            ║"
echo "║    sudo systemctl status loopcanvas                   ║"
echo "║    sudo journalctl -u loopcanvas -f                   ║"
echo "║    sudo systemctl restart loopcanvas                  ║"
echo "╚══════════════════════════════════════════════════════╝"
