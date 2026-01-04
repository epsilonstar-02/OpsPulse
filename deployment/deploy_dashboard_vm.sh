#!/bin/bash
# ============================================================
# OpsPulse AI - VM 4: Dashboard API + Pathway Consumer Setup
# ============================================================
# Run this script on the opspulse-dashboard VM
# Usage: chmod +x deploy_dashboard_vm.sh && ./deploy_dashboard_vm.sh
# ============================================================

set -e

echo "=========================================="
echo "📊 OpsPulse AI - Dashboard API Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

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
    python3-certbot-nginx \
    build-essential

# Step 3: Create Application Directory
log_info "Setting up application directory..."
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Step 4: Create Virtual Environment
log_info "Creating Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Step 5: Install Python Dependencies
log_info "Installing Python dependencies..."
pip install --upgrade pip

# Dashboard API requirements
pip install -r $APP_DIR/backend/requirements.txt

# Pathway and Kafka requirements
pip install -r $APP_DIR/Message_queue_kafka/requirements.txt
pip install pathway

# Step 6: Create Environment File
log_info "Creating environment file..."
if [ ! -f "$APP_DIR/.env" ]; then
    cat > $APP_DIR/.env << 'EOF'
# OpsPulse Dashboard Configuration
DEBUG=false
ENVIRONMENT=production

# Service URLs (UPDATE THESE WITH ACTUAL IPs)
LOG_GENERATOR_URL=http://10.0.0.2:8000
RAG_SERVER_URL=http://10.0.0.3:5000
DEEPSEEK_URL=http://10.0.0.4:8080

# Kafka/Redpanda Configuration
KAFKA_USERNAME=ashutosh
KAFKA_PASSWORD=768581

# Dashboard API Settings
HOST=0.0.0.0
PORT=8001

# Data retention
METRICS_HISTORY_MINUTES=60
MAX_RECENT_LOGS=1000
MAX_RECENT_ALERTS=500
EOF
    log_warn "Created .env file. Please update service URLs with actual IPs!"
fi

# Step 7: Create Dashboard API Service
log_info "Creating systemd service for Dashboard API..."
sudo tee /etc/systemd/system/opspulse-dashboard.service << EOF
[Unit]
Description=OpsPulse Dashboard API
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 8: Create Pathway Consumer Service
log_info "Creating systemd service for Pathway Consumer..."
sudo tee /etc/systemd/system/opspulse-pathway.service << EOF
[Unit]
Description=OpsPulse Pathway Consumer
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python Message_queue_kafka/pathway_consumer.py --rag-url \${RAG_SERVER_URL}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Step 9: Configure Nginx
log_info "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/opspulse-dashboard << 'EOF'
upstream dashboard_api {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name _;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Increase timeouts for WebSocket
    proxy_connect_timeout 7d;
    proxy_send_timeout 7d;
    proxy_read_timeout 7d;

    # Buffer sizes
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    # API endpoints
    location / {
        proxy_pass http://dashboard_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket endpoint
    location /ws/ {
        proxy_pass http://dashboard_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # Health check
    location /health {
        proxy_pass http://dashboard_api/health;
        proxy_http_version 1.1;
        access_log off;
    }

    # Metrics endpoint (restrict in production)
    location /api/system/metrics {
        proxy_pass http://dashboard_api;
        proxy_http_version 1.1;
        # Uncomment to restrict access:
        # allow 10.0.0.0/24;
        # deny all;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/opspulse-dashboard /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Step 10: Enable and Start Services
log_info "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable opspulse-dashboard opspulse-pathway nginx

# Start Dashboard API
sudo systemctl start opspulse-dashboard

# Wait for API to be ready before starting Pathway
log_info "Waiting for Dashboard API to be ready..."
sleep 10

# Start Pathway Consumer
sudo systemctl start opspulse-pathway

# Step 11: Verify Services
log_info "Verifying services..."
echo ""
echo "=========================================="
echo "Service Status:"
echo "=========================================="
sudo systemctl status opspulse-dashboard --no-pager -l || true
echo ""
sudo systemctl status opspulse-pathway --no-pager -l || true
echo ""

# Test API
log_info "Testing Dashboard API..."
sleep 3
if curl -s http://localhost:8001/health > /dev/null; then
    log_info "✅ Dashboard API is responding!"
    echo ""
    echo "API Response:"
    curl -s http://localhost:8001/health | python3 -m json.tool
else
    log_warn "⚠️ Dashboard API may not be ready yet. Check logs."
fi

# Get external IP
EXTERNAL_IP=$(curl -s ifconfig.me)

echo ""
echo "=========================================="
echo "🎉 Deployment Complete!"
echo "=========================================="
echo ""
echo "Dashboard API: http://$EXTERNAL_IP"
echo "API Documentation: http://$EXTERNAL_IP/docs"
echo "WebSocket: ws://$EXTERNAL_IP/ws/live"
echo ""
echo "Useful commands:"
echo "  View Dashboard logs: sudo journalctl -u opspulse-dashboard -f"
echo "  View Pathway logs:   sudo journalctl -u opspulse-pathway -f"
echo "  Restart services:    sudo systemctl restart opspulse-dashboard opspulse-pathway"
echo ""
echo "⚠️  Next steps:"
echo "  1. Update .env with actual service IPs"
echo "  2. Configure SSL: sudo certbot --nginx -d your-domain.com"
echo "  3. Configure firewall for production"
echo ""
echo "=========================================="
