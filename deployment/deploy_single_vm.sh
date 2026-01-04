#!/bin/bash
# ============================================================
# OpsPulse AI - Quick Deployment Script (Single VM)
# ============================================================
# For development/testing: Deploy all services on a single VM
# Minimum: e2-standard-4 (4 vCPU, 16GB RAM)
# Usage: chmod +x deploy_single_vm.sh && ./deploy_single_vm.sh
# ============================================================

set -e

echo "=========================================="
echo "🚀 OpsPulse AI - Single VM Deployment"
echo "=========================================="
echo ""
echo "This will deploy ALL services on a single VM:"
echo "  - Log Generator (port 8000)"
echo "  - Kafka Producer"
echo "  - RAG Server (port 5000)"
echo "  - Dashboard API (port 8001)"
echo "  - Pathway Consumer"
echo ""
echo "Recommended VM: e2-standard-4 or larger"
echo ""

# Colors
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

# Check system resources
MEM_GB=$(free -g | awk '/^Mem:/{print $2}')
CPU_COUNT=$(nproc)

log_info "System: ${CPU_COUNT} CPUs, ${MEM_GB}GB RAM"

if [ "$MEM_GB" -lt 8 ]; then
    log_warn "Warning: Less than 8GB RAM detected. Some services may fail."
fi

read -p "Continue with deployment? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# ==================== STEP 1: System Setup ====================

log_info "Step 1: Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

log_info "Installing system dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    nginx \
    certbot \
    python3-certbot-nginx \
    build-essential \
    supervisor

# ==================== STEP 2: Application Setup ====================

log_info "Step 2: Setting up application directory..."
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Check if code exists
if [ ! -f "$APP_DIR/main.py" ]; then
    log_error "Application code not found in $APP_DIR"
    log_info "Please clone your repository first:"
    echo "  git clone https://github.com/YOUR_USERNAME/OpsPulse.git $APP_DIR"
    exit 1
fi

# ==================== STEP 3: Virtual Environment ====================

log_info "Step 3: Creating Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

log_info "Installing Python dependencies..."
pip install --upgrade pip

# Install all requirements
pip install -r $APP_DIR/logs_generator/requirements.txt
pip install -r $APP_DIR/Message_queue_kafka/requirements.txt
pip install -r $APP_DIR/Rag/requirements.txt
pip install -r $APP_DIR/backend/requirements.txt
pip install pathway pdfplumber chromadb

# ==================== STEP 4: Environment Configuration ====================

log_info "Step 4: Creating environment file..."
cat > $APP_DIR/.env << 'EOF'
# OpsPulse Single VM Configuration
DEBUG=false
ENVIRONMENT=production

# Google API Key (REQUIRED for RAG embeddings)
GOOGLE_API_KEY=your_google_api_key_here

# Service URLs (localhost for single VM)
LOG_GENERATOR_URL=http://localhost:8000
RAG_SERVER_URL=http://localhost:5000
DEEPSEEK_URL=http://localhost:8080

# Kafka credentials
KAFKA_USERNAME=ashutosh
KAFKA_PASSWORD=768581

# Dashboard settings
HOST=0.0.0.0
PORT=8001
METRICS_HISTORY_MINUTES=60
MAX_RECENT_LOGS=1000
EOF

log_warn "⚠️  Update GOOGLE_API_KEY in $APP_DIR/.env"

# ==================== STEP 5: Create Systemd Services ====================

log_info "Step 5: Creating systemd services..."

# Log Generator
sudo tee /etc/systemd/system/opspulse-logs.service << EOF
[Unit]
Description=OpsPulse Log Generator
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn logs_generator.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Kafka Producer
sudo tee /etc/systemd/system/opspulse-producer.service << EOF
[Unit]
Description=OpsPulse Kafka Producer
After=network.target opspulse-logs.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python Message_queue_kafka/producer.py --continuous --server http://localhost:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# RAG Server
sudo tee /etc/systemd/system/opspulse-rag.service << EOF
[Unit]
Description=OpsPulse RAG Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python -m Rag.server --host 0.0.0.0 --port 5000 --ingest
Restart=always
RestartSec=30
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOF

# Dashboard API
sudo tee /etc/systemd/system/opspulse-dashboard.service << EOF
[Unit]
Description=OpsPulse Dashboard API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Pathway Consumer
sudo tee /etc/systemd/system/opspulse-pathway.service << EOF
[Unit]
Description=OpsPulse Pathway Consumer
After=network.target opspulse-rag.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python Message_queue_kafka/pathway_consumer.py --rag-url http://localhost:5000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# ==================== STEP 6: Configure Nginx ====================

log_info "Step 6: Configuring Nginx..."

sudo tee /etc/nginx/sites-available/opspulse << 'EOF'
# Log Generator
upstream logs_api {
    server 127.0.0.1:8000;
}

# RAG Server
upstream rag_api {
    server 127.0.0.1:5000;
}

# Dashboard API
upstream dashboard_api {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name _;

    # Timeouts for WebSocket
    proxy_connect_timeout 7d;
    proxy_send_timeout 7d;
    proxy_read_timeout 7d;

    # Dashboard API (default)
    location / {
        proxy_pass http://dashboard_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://dashboard_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # Log Generator API
    location /logs/ {
        rewrite ^/logs/(.*)$ /$1 break;
        proxy_pass http://logs_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # RAG API
    location /rag/ {
        rewrite ^/rag/(.*)$ /$1 break;
        proxy_pass http://rag_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_read_timeout 300;
    }

    # Direct port access (for development)
    location /port/8000/ {
        rewrite ^/port/8000/(.*)$ /$1 break;
        proxy_pass http://logs_api;
    }

    location /port/5000/ {
        rewrite ^/port/5000/(.*)$ /$1 break;
        proxy_pass http://rag_api;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/opspulse /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# ==================== STEP 7: Enable and Start Services ====================

log_info "Step 7: Enabling services..."
sudo systemctl daemon-reload

# Enable all services
sudo systemctl enable opspulse-logs opspulse-producer opspulse-rag opspulse-dashboard opspulse-pathway nginx

log_info "Starting services (this may take a few minutes)..."

# Start in order
sudo systemctl start opspulse-logs
sleep 5

sudo systemctl start opspulse-dashboard
sleep 3

# These can start in parallel
sudo systemctl start opspulse-producer &
sudo systemctl start opspulse-rag &
wait

# Wait for RAG to be ready
log_info "Waiting for RAG server to initialize..."
sleep 30

sudo systemctl start opspulse-pathway

# ==================== STEP 8: Verify ====================

log_info "Step 8: Verifying services..."
echo ""
echo "=========================================="
echo "Service Status:"
echo "=========================================="

for service in logs producer rag dashboard pathway; do
    status=$(sudo systemctl is-active opspulse-$service 2>/dev/null || echo "inactive")
    if [ "$status" == "active" ]; then
        echo -e "opspulse-$service: ${GREEN}✓ active${NC}"
    else
        echo -e "opspulse-$service: ${RED}✗ $status${NC}"
    fi
done

echo ""
echo "=========================================="
echo "API Health Checks:"
echo "=========================================="

# Test endpoints
for port in 8000 5000 8001; do
    if curl -s http://localhost:$port/health > /dev/null 2>&1 || curl -s http://localhost:$port/ > /dev/null 2>&1; then
        echo -e "Port $port: ${GREEN}✓ responding${NC}"
    else
        echo -e "Port $port: ${YELLOW}⚠ not ready${NC}"
    fi
done

# Get external IP
EXTERNAL_IP=$(curl -s ifconfig.me 2>/dev/null || echo "unknown")

echo ""
echo "=========================================="
echo "🎉 Deployment Complete!"
echo "=========================================="
echo ""
echo "External IP: $EXTERNAL_IP"
echo ""
echo "Service URLs:"
echo "  Dashboard API:  http://$EXTERNAL_IP/"
echo "  API Docs:       http://$EXTERNAL_IP/docs"
echo "  WebSocket:      ws://$EXTERNAL_IP/ws/live"
echo "  Log Generator:  http://$EXTERNAL_IP:8000/"
echo "  RAG Server:     http://$EXTERNAL_IP:5000/"
echo ""
echo "Useful Commands:"
echo "  View all logs:  sudo journalctl -u 'opspulse-*' -f"
echo "  Restart all:    sudo systemctl restart opspulse-{logs,producer,rag,dashboard,pathway}"
echo "  Service status: sudo systemctl status opspulse-*"
echo ""
echo "⚠️  Remember to:"
echo "  1. Update GOOGLE_API_KEY in $APP_DIR/.env"
echo "  2. Add runbook PDFs to $APP_DIR/run book/"
echo "  3. Configure SSL: sudo certbot --nginx"
echo ""
echo "=========================================="
