#!/bin/bash
# ============================================================
# OpsPulse AI - VM 2: RAG Server Setup
# ============================================================
# Run this script on the opspulse-rag VM
# Usage: chmod +x deploy_rag_vm.sh && ./deploy_rag_vm.sh
# ============================================================

set -e

echo "=========================================="
echo "🧠 OpsPulse AI - RAG Server Deployment"
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
RUNBOOK_DIR="$APP_DIR/run book"
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
    build-essential \
    libffi-dev \
    libssl-dev

# Step 3: Create Application Directory
log_info "Setting up application directory..."
sudo mkdir -p "$APP_DIR"
sudo mkdir -p "$RUNBOOK_DIR"
sudo chown -R $USER:$USER "$APP_DIR"

# Step 4: Create Virtual Environment
log_info "Creating Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Step 5: Install Python Dependencies
log_info "Installing Python dependencies (this may take a while)..."
pip install --upgrade pip

# RAG requirements
pip install -r $APP_DIR/Rag/requirements.txt

# Additional dependencies for PDF processing
pip install pdfplumber chromadb litellm pathway

# Step 6: Create Environment File
log_info "Creating environment file..."
if [ ! -f "$APP_DIR/.env" ]; then
    cat > $APP_DIR/.env << 'EOF'
# OpsPulse RAG Server Configuration
DEBUG=false
ENVIRONMENT=production

# Google API Key for Gemini Embeddings (REQUIRED)
GOOGLE_API_KEY=your_google_api_key_here

# DeepSeek LLM Configuration
# If using hosted DeepSeek API:
# DEEPSEEK_API_KEY=your_deepseek_api_key
# DEEPSEEK_API_BASE=https://api.deepseek.com/v1

# If using self-hosted LLM:
DEEPSEEK_URL=http://10.0.0.4:8080
EOF
    log_warn "Created .env file. Please update GOOGLE_API_KEY!"
fi

# Step 7: Create RAG Configuration
log_info "Creating RAG configuration..."
cat > $APP_DIR/Rag/config.yaml << 'EOF'
# RAG Pipeline Configuration

embedding:
  model: "gemini/text-embedding-004"
  dimension: 3072
  # api_key loaded from GOOGLE_API_KEY env var

llm:
  model: "deepseek/deepseek-r1"
  api_base: "http://10.0.0.4:8080"  # Update with LLM VM IP
  temperature: 0
  top_p: 1

documents:
  chunk_size: 1000
  chunk_overlap: 200

server:
  host: "0.0.0.0"
  port: 5000
EOF

# Step 8: Create RAG Server Service
log_info "Creating systemd service for RAG Server..."
sudo tee /etc/systemd/system/opspulse-rag.service << EOF
[Unit]
Description=OpsPulse RAG Server
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python -m Rag.server --host 0.0.0.0 --port 5000 --ingest
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
# RAG needs more time to start (PDF processing)
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
EOF

# Step 9: Configure Nginx
log_info "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/opspulse-rag << 'EOF'
upstream rag_server {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name _;

    # Increase timeouts for RAG queries
    proxy_connect_timeout 300;
    proxy_send_timeout 300;
    proxy_read_timeout 300;
    send_timeout 300;

    location / {
        proxy_pass http://rag_server;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /health {
        proxy_pass http://rag_server/health;
        proxy_connect_timeout 5;
        proxy_read_timeout 5;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/opspulse-rag /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Step 10: Check for PDF runbooks
log_info "Checking for runbook PDFs..."
if [ -z "$(ls -A "$RUNBOOK_DIR"/*.pdf 2>/dev/null)" ]; then
    log_warn "No PDF files found in '$RUNBOOK_DIR'"
    log_warn "Please upload your runbook PDFs to this directory"
    log_warn "Example: scp your_runbook.pdf user@this-vm:$RUNBOOK_DIR/"
else
    log_info "Found PDF files:"
    ls -la "$RUNBOOK_DIR"/*.pdf
fi

# Step 11: Enable Services
log_info "Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable opspulse-rag nginx

echo ""
echo "=========================================="
echo "⚠️  IMPORTANT: Before starting the RAG server:"
echo "=========================================="
echo ""
echo "1. Update the Google API key in $APP_DIR/.env"
echo "   GOOGLE_API_KEY=your_actual_key"
echo ""
echo "2. Upload your runbook PDFs to:"
echo "   $RUNBOOK_DIR/"
echo ""
echo "3. Update the LLM URL in Rag/config.yaml"
echo "   api_base: http://YOUR_LLM_VM_IP:8080"
echo ""
echo "Then start the service:"
echo "   sudo systemctl start opspulse-rag"
echo ""
echo "Monitor startup with:"
echo "   sudo journalctl -u opspulse-rag -f"
echo ""
echo "=========================================="
echo "🎉 RAG Server Setup Complete!"
echo "=========================================="
