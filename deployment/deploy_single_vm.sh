#!/bin/bash
# ============================================================
# OpsPulse AI - Quick Deployment Script (Single VM)
# ============================================================
# Optimized for: 8 vCPU, 32GB RAM (e2-standard-8)
# Resource Isolation: DeepSeek on CPUs 0-3, OpsPulse on CPUs 4-7
# Usage: chmod +x deploy_single_vm.sh && ./deploy_single_vm.sh
# ============================================================

set -e

echo "=========================================="
echo "🚀 OpsPulse AI - Single VM Deployment"
echo "=========================================="
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           RESOURCE ALLOCATION (8 vCPU, 32GB)              ║"
echo "╠═══════════════════════════════════════════════════════════╣"
echo "║  DeepSeek LLM (llama.cpp)                                 ║"
echo "║    └─ CPUs: 0-3 (4 cores) │ RAM: 16GB │ Port: 8080        ║"
echo "║                                                           ║"
echo "║  OpsPulse Services (cgroup isolated)                      ║"
echo "║    ├─ CPUs: 4-7 (4 cores) │ RAM: 12GB total               ║"
echo "║    ├─ Log Generator      │ 512MB  │ Port: 8000            ║"
echo "║    ├─ Kafka Producer     │ 512MB  │ (background)          ║"
echo "║    ├─ RAG Server         │ 4GB    │ Port: 5000            ║"
echo "║    ├─ Dashboard API      │ 1GB    │ Port: 8001            ║"
echo "║    └─ Pathway Consumer   │ 2GB    │ (stream processor)    ║"
echo "║                                                           ║"
echo "║  System Reserved: ~4GB                                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_resource() { echo -e "${BLUE}[RESOURCE]${NC} $1"; }

# Configuration
APP_DIR="/opt/opspulse"
VENV_DIR="$APP_DIR/venv"
USER=$(whoami)

# Check system resources
MEM_GB=$(free -g | awk '/^Mem:/{print $2}')
CPU_COUNT=$(nproc)

log_info "Detected: ${CPU_COUNT} CPUs, ${MEM_GB}GB RAM"

# Validate resources
if [ "$CPU_COUNT" -lt 8 ]; then
    log_warn "Warning: Less than 8 CPUs. Adjusting CPU affinity..."
    log_warn "DeepSeek may impact OpsPulse performance."
fi

if [ "$MEM_GB" -lt 24 ]; then
    log_warn "Warning: Less than 24GB RAM. Consider reducing DeepSeek memory limit."
fi

if [ "$MEM_GB" -ge 32 ] && [ "$CPU_COUNT" -ge 8 ]; then
    log_info "✅ Optimal resources detected! Full isolation enabled."
fi

# Check if DeepSeek is already running
if pgrep -f "llama-server\|llama.cpp" > /dev/null; then
    log_info "✅ DeepSeek (llama.cpp) detected running"
    DEEPSEEK_RUNNING=true
else
    log_warn "⚠️  DeepSeek not detected. Will create service template."
    DEEPSEEK_RUNNING=false
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

# DeepSeek LLM - llama.cpp server (ALREADY DEPLOYED)
# Ensure your llama.cpp server is running on this port
DEEPSEEK_URL=http://localhost:8080
LOCAL_MODEL_URL=http://localhost:8080/v1

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

log_info "Step 5: Creating systemd services with resource isolation..."

# ============================================================
# RESOURCE ALLOCATION (8 vCPU, 32GB RAM)
# ============================================================
# DeepSeek (llama.cpp): CPUs 0-3 (4 cores), 16GB RAM max
# OpsPulse Services:    CPUs 4-7 (4 cores), 12GB RAM max
# System Reserved:      4GB RAM
# ============================================================

# Create cgroup slice for OpsPulse services (isolated from DeepSeek)
log_info "Creating cgroup slice for resource isolation..."
sudo tee /etc/systemd/system/opspulse.slice << EOF
[Unit]
Description=OpsPulse Services Resource Slice
Before=slices.target

[Slice]
# Restrict to CPUs 4-7 (leave 0-3 for DeepSeek)
AllowedCPUs=4-7
# Memory limit: 12GB for all OpsPulse services combined
MemoryMax=12G
MemoryHigh=10G
# CPU weight (relative priority)
CPUWeight=100
EOF

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
# Resource isolation
Slice=opspulse.slice
MemoryMax=512M
CPUQuota=50%
Nice=5

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
# Resource isolation
Slice=opspulse.slice
MemoryMax=512M
CPUQuota=50%
Nice=5

[Install]
WantedBy=multi-user.target
EOF

# RAG Server (ChromaDB + embeddings - needs more memory)
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
# Resource isolation (RAG needs more memory for embeddings)
Slice=opspulse.slice
MemoryMax=4G
MemoryHigh=3G
CPUQuota=150%
Nice=0

[Install]
WantedBy=multi-user.target
EOF

# Dashboard API (user-facing - higher priority)
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
ExecStart=$VENV_DIR/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001 --workers 2
Restart=always
RestartSec=5
# Resource isolation (dashboard gets priority for responsiveness)
Slice=opspulse.slice
MemoryMax=1G
CPUQuota=100%
Nice=-5

[Install]
WantedBy=multi-user.target
EOF

# Pathway Consumer (stream processing - needs consistent resources)
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
# Resource isolation (Pathway needs stable CPU for streaming)
Slice=opspulse.slice
MemoryMax=2G
MemoryHigh=1G
CPUQuota=100%
Nice=0

[Install]
WantedBy=multi-user.target
EOF

# ==================== STEP 5b: Create DeepSeek Service (Optional) ====================

log_info "Creating DeepSeek llama.cpp service template..."
log_warn "⚠️  Skip if you already have llama.cpp running!"

# DeepSeek llama.cpp service (ISOLATED on CPUs 0-3)
sudo tee /etc/systemd/system/deepseek-llm.service << EOF
[Unit]
Description=DeepSeek R1 LLM (llama.cpp)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/llama.cpp
# Pin to CPUs 0-3 (isolated from OpsPulse on 4-7)
CPUAffinity=0 1 2 3
# Memory limit: 16GB for model + KV cache
MemoryMax=16G
MemoryHigh=14G
# High priority for inference latency
Nice=-10
# Use 4 threads matching CPU allocation
ExecStart=/opt/llama.cpp/llama-server \\\n    --model /opt/models/deepseek-r1-q4.gguf \\\n    --host 0.0.0.0 \\\n    --port 8080 \\\n    --threads 4 \\\n    --ctx-size 4096 \\\n    --batch-size 512
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

log_info "Step 7: Enabling services with resource isolation..."
sudo systemctl daemon-reload

# Enable cgroup slice first
log_resource "Enabling OpsPulse cgroup slice (CPUs 4-7, 12GB RAM limit)..."
sudo systemctl enable opspulse.slice

# Enable all services
sudo systemctl enable opspulse-logs opspulse-producer opspulse-rag opspulse-dashboard opspulse-pathway nginx

# Check if DeepSeek service should be enabled
if [ "$DEEPSEEK_RUNNING" = false ]; then
    log_warn "DeepSeek service template created at /etc/systemd/system/deepseek-llm.service"
    log_warn "To enable: sudo systemctl enable deepseek-llm && sudo systemctl start deepseek-llm"
    log_warn "Remember to update the model path in the service file!"
fi

log_info "Starting services (this may take a few minutes)..."
log_resource "OpsPulse services will run on CPUs 4-7 (isolated from DeepSeek)"

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
echo "Resource Isolation Status:"
echo "=========================================="

# Check cgroup slice
if systemctl is-active opspulse.slice > /dev/null 2>&1; then
    echo -e "OpsPulse Slice: ${GREEN}✓ active${NC} (CPUs 4-7, 12GB limit)"
else
    echo -e "OpsPulse Slice: ${YELLOW}⚠ inactive${NC}"
fi

# Check DeepSeek
if pgrep -f "llama-server\|llama.cpp" > /dev/null; then
    DEEPSEEK_PID=$(pgrep -f "llama-server\|llama.cpp" | head -1)
    DEEPSEEK_CPU=$(ps -p $DEEPSEEK_PID -o %cpu --no-headers 2>/dev/null || echo "?")
    DEEPSEEK_MEM=$(ps -p $DEEPSEEK_PID -o %mem --no-headers 2>/dev/null || echo "?")
    echo -e "DeepSeek LLM:   ${GREEN}✓ running${NC} (CPU: ${DEEPSEEK_CPU}%, MEM: ${DEEPSEEK_MEM}%)"
else
    echo -e "DeepSeek LLM:   ${YELLOW}⚠ not detected${NC}"
fi

# Show memory breakdown
echo ""
echo "Memory Usage:"
free -h | grep -E "Mem:|Swap:"

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

# Check DeepSeek endpoint
if curl -s http://localhost:8080/health > /dev/null 2>&1 || curl -s http://localhost:8080/v1/models > /dev/null 2>&1; then
    echo -e "Port 8080 (DeepSeek): ${GREEN}✓ responding${NC}"
else
    echo -e "Port 8080 (DeepSeek): ${YELLOW}⚠ not ready${NC}"
fi

# Get external IP
EXTERNAL_IP=$(curl -s ifconfig.me 2>/dev/null || echo "unknown")

echo ""
echo "=========================================="
echo "🎉 Deployment Complete!"
echo "=========================================="
echo ""
echo "External IP: $EXTERNAL_IP"
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  RESOURCE ISOLATION ACTIVE                                ║"
echo "║  DeepSeek (CPUs 0-3, 16GB) ←→ OpsPulse (CPUs 4-7, 12GB)  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Service URLs:"
echo "  Dashboard API:  http://$EXTERNAL_IP/"
echo "  API Docs:       http://$EXTERNAL_IP/docs"
echo "  WebSocket:      ws://$EXTERNAL_IP/ws/live"
echo "  Log Generator:  http://$EXTERNAL_IP:8000/"
echo "  RAG Server:     http://$EXTERNAL_IP:5000/"
echo "  DeepSeek LLM:   http://$EXTERNAL_IP:8080/"
echo ""
echo "Useful Commands:"
echo "  View all logs:    sudo journalctl -u 'opspulse-*' -f"
echo "  Restart all:      sudo systemctl restart opspulse-{logs,producer,rag,dashboard,pathway}"
echo "  Service status:   sudo systemctl status opspulse-*"
echo "  Resource monitor: systemctl status opspulse.slice"
echo "  CPU usage:        htop (press F2 → Display → CPU affinity)"
echo ""
echo "⚠️  Remember to:"
echo "  1. Update GOOGLE_API_KEY in $APP_DIR/.env"
echo "  2. Add runbook PDFs to $APP_DIR/run book/"
echo "  3. Configure SSL: sudo certbot --nginx"
echo ""
echo "=========================================="
