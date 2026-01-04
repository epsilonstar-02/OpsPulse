#!/bin/bash
# ============================================================
# OpsPulse AI - VM 1: Log Generator + Producer Setup
# ============================================================
# Run this script on the opspulse-logs VM
# Usage: chmod +x deploy_logs_vm.sh && ./deploy_logs_vm.sh
# ============================================================

set -e

echo "=========================================="
echo "🚀 OpsPulse AI - Log Generator Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    log_error "Please do not run as root. Run as regular user with sudo privileges."
    exit 1
fi

# Configuration
APP_DIR="/opt/opspulse"
VENV_DIR="$APP_DIR/venv"
USER=$(whoami)

# Step 1: System Update
log_info "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Step 2: Install Dependencies
log_info "Installing system dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    nginx \
    certbot \
    python3-certbot-nginx

# Step 3: Create Application Directory
log_info "Setting up application directory..."
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Step 4: Clone Repository (or copy files)
log_info "Setting up application code..."
if [ -d "$APP_DIR/.git" ]; then
    cd $APP_DIR
    git pull origin main
else
    # If not a git repo, assume files are already there or need to be copied
    log_warn "Git repository not found. Please ensure code is in $APP_DIR"
fi

# Step 5: Create Virtual Environment
log_info "Creating Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Step 6: Install Python Dependencies
log_info "Installing Python dependencies..."
pip install --upgrade pip
pip install -r $APP_DIR/logs_generator/requirements.txt
pip install -r $APP_DIR/Message_queue_kafka/requirements.txt

# Step 7: Create Environment File
log_info "Creating environment file..."
if [ ! -f "$APP_DIR/.env" ]; then
    cat > $APP_DIR/.env << 'EOF'
# OpsPulse Environment Configuration
DEBUG=false
ENVIRONMENT=production

# Add your Google API key for embeddings (if needed)
# GOOGLE_API_KEY=your_key_here

# Kafka credentials (update if different)
KAFKA_USERNAME=ashutosh
KAFKA_PASSWORD=768581
EOF
    log_warn "Created .env file. Please update with your actual credentials!"
fi

# Step 8: Create Log Generator Service
log_info "Creating systemd service for Log Generator..."
sudo tee /etc/systemd/system/opspulse-logs.service << EOF
[Unit]
Description=OpsPulse Log Generator API
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn logs_generator.server:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 9: Create Kafka Producer Service
log_info "Creating systemd service for Kafka Producer..."
sudo tee /etc/systemd/system/opspulse-producer.service << EOF
[Unit]
Description=OpsPulse Kafka Producer
After=network.target opspulse-logs.service
Requires=opspulse-logs.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python Message_queue_kafka/producer.py --continuous --server http://localhost:8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 10: Configure Nginx
log_info "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/opspulse-logs << 'EOF'
upstream log_generator {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name _;

    # Increase buffer sizes
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    location / {
        proxy_pass http://log_generator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://log_generator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/opspulse-logs /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Step 11: Enable and Start Services
log_info "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable opspulse-logs opspulse-producer nginx
sudo systemctl start opspulse-logs
sleep 5  # Wait for log generator to be ready
sudo systemctl start opspulse-producer

# Step 12: Verify Services
log_info "Verifying services..."
echo ""
echo "=========================================="
echo "Service Status:"
echo "=========================================="
sudo systemctl status opspulse-logs --no-pager -l || true
echo ""
sudo systemctl status opspulse-producer --no-pager -l || true
echo ""

# Test API
log_info "Testing Log Generator API..."
sleep 3
if curl -s http://localhost:8000/api/status > /dev/null; then
    log_info "✅ Log Generator API is responding!"
else
    log_warn "⚠️ Log Generator API may not be ready yet. Check logs."
fi

echo ""
echo "=========================================="
echo "🎉 Deployment Complete!"
echo "=========================================="
echo ""
echo "Log Generator API: http://$(curl -s ifconfig.me):8000"
echo "API Documentation: http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo "Useful commands:"
echo "  View logs:    sudo journalctl -u opspulse-logs -f"
echo "  View producer: sudo journalctl -u opspulse-producer -f"
echo "  Restart:      sudo systemctl restart opspulse-logs opspulse-producer"
echo ""
echo "⚠️  Remember to configure SSL with: sudo certbot --nginx"
echo "=========================================="
