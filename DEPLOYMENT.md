# 🚀 OpsPulse AI - Complete GCP Deployment Guide

> **Production Deployment for Real-Time Log Analysis & Automated Remediation System**

This guide covers deploying all OpsPulse AI services on Google Cloud Platform (GCP) Virtual Machines.

---

## 📑 Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [GCP Infrastructure Setup](#3-gcp-infrastructure-setup)
4. [VM Configuration](#4-vm-configuration)
5. [Service Deployments](#5-service-deployments)
6. [Nginx Reverse Proxy](#6-nginx-reverse-proxy)
7. [SSL/TLS Configuration](#7-ssltls-configuration)
8. [Firewall Rules](#8-firewall-rules)
9. [Monitoring & Logging](#9-monitoring--logging)
10. [Maintenance & Troubleshooting](#10-maintenance--troubleshooting)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GCP PROJECT                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         VPC Network                                      ││
│  │                                                                          ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ ││
│  │  │  VM 1        │  │  VM 2        │  │  VM 3        │  │  VM 4        │ ││
│  │  │  Log Gen     │  │  RAG Server  │  │  DeepSeek    │  │  Dashboard   │ ││
│  │  │  :8000       │  │  :5000       │  │  :8080       │  │  API :8001   │ ││
│  │  │  Producer    │  │  ChromaDB    │  │  LLM         │  │  Pathway     │ ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ ││
│  │         │                 │                 │                 │         ││
│  │         └─────────────────┴─────────────────┴─────────────────┘         ││
│  │                                   │                                      ││
│  │                    ┌──────────────┴──────────────┐                      ││
│  │                    │   Kafka/Redpanda (Cloud)    │                      ││
│  │                    │   - raw_logs                │                      ││
│  │                    │   - processed_alerts        │                      ││
│  │                    │   - remediation_alerts      │                      ││
│  │                    └─────────────────────────────┘                      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────┐                              ┌─────────────────┐       │
│  │  Cloud Load     │◄────── HTTPS ──────────────►│  Cloud DNS      │       │
│  │  Balancer       │                              │  opspulse.ai    │       │
│  └─────────────────┘                              └─────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Services Overview

| Service | Port | VM Recommendation | Purpose |
|---------|------|-------------------|---------|
| **Log Generator** | 8000 | e2-small (2 vCPU, 2GB) | Synthetic log generation |
| **Kafka Producer** | - | Same as Log Generator | Sends logs to Kafka |
| **RAG Server** | 5000 | e2-standard-4 (4 vCPU, 16GB) | ChromaDB + Embeddings |
| **DeepSeek LLM** | 8080 | n1-standard-8 + GPU (optional) | Reasoning LLM |
| **Dashboard API** | 8001 | e2-medium (2 vCPU, 4GB) | Dashboard backend |
| **Pathway Consumer** | - | Same as Dashboard API | Stream processing |

---

## 2. Prerequisites

### 2.1 GCP Account & Project

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Initialize and authenticate
gcloud init
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID
```

### 2.2 Enable Required APIs

```bash
gcloud services enable compute.googleapis.com
gcloud services enable dns.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com
```

### 2.3 Required Credentials

Ensure you have:
- `GOOGLE_API_KEY` - For Gemini embeddings
- Kafka/Redpanda credentials (already configured in code)
- (Optional) Domain name for SSL

---

## 3. GCP Infrastructure Setup

### 3.1 Create VPC Network

```bash
# Create VPC
gcloud compute networks create opspulse-vpc \
    --subnet-mode=custom \
    --bgp-routing-mode=regional

# Create subnet
gcloud compute networks subnets create opspulse-subnet \
    --network=opspulse-vpc \
    --region=us-central1 \
    --range=10.0.0.0/24
```

### 3.2 Create Firewall Rules

```bash
# Allow internal communication
gcloud compute firewall-rules create opspulse-internal \
    --network=opspulse-vpc \
    --allow=tcp:0-65535,udp:0-65535,icmp \
    --source-ranges=10.0.0.0/24

# Allow SSH
gcloud compute firewall-rules create opspulse-ssh \
    --network=opspulse-vpc \
    --allow=tcp:22 \
    --source-ranges=0.0.0.0/0

# Allow HTTP/HTTPS
gcloud compute firewall-rules create opspulse-http \
    --network=opspulse-vpc \
    --allow=tcp:80,tcp:443 \
    --source-ranges=0.0.0.0/0

# Allow application ports (for testing - restrict in production)
gcloud compute firewall-rules create opspulse-apps \
    --network=opspulse-vpc \
    --allow=tcp:8000,tcp:8001,tcp:5000,tcp:8080 \
    --source-ranges=0.0.0.0/0
```

### 3.3 Create VM Instances

```bash
# VM 1: Log Generator + Producer
gcloud compute instances create opspulse-logs \
    --zone=us-central1-a \
    --machine-type=e2-small \
    --network=opspulse-vpc \
    --subnet=opspulse-subnet \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --tags=opspulse-logs

# VM 2: RAG Server
gcloud compute instances create opspulse-rag \
    --zone=us-central1-a \
    --machine-type=e2-standard-4 \
    --network=opspulse-vpc \
    --subnet=opspulse-subnet \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB \
    --tags=opspulse-rag

# VM 3: DeepSeek LLM (or connect to external API)
gcloud compute instances create opspulse-llm \
    --zone=us-central1-a \
    --machine-type=n1-standard-4 \
    --network=opspulse-vpc \
    --subnet=opspulse-subnet \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=100GB \
    --tags=opspulse-llm

# VM 4: Dashboard API + Pathway Consumer
gcloud compute instances create opspulse-dashboard \
    --zone=us-central1-a \
    --machine-type=e2-medium \
    --network=opspulse-vpc \
    --subnet=opspulse-subnet \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --tags=opspulse-dashboard
```

### 3.4 Reserve Static IPs

```bash
# Reserve external IPs for public-facing services
gcloud compute addresses create opspulse-logs-ip --region=us-central1
gcloud compute addresses create opspulse-dashboard-ip --region=us-central1

# Assign to VMs
gcloud compute instances add-access-config opspulse-logs \
    --zone=us-central1-a \
    --address=$(gcloud compute addresses describe opspulse-logs-ip --region=us-central1 --format='get(address)')

gcloud compute instances add-access-config opspulse-dashboard \
    --zone=us-central1-a \
    --address=$(gcloud compute addresses describe opspulse-dashboard-ip --region=us-central1 --format='get(address)')
```

---

## 4. VM Configuration

### 4.1 Base Setup Script (Run on ALL VMs)

```bash
#!/bin/bash
# base_setup.sh - Run on all VMs

set -e

echo "=========================================="
echo "OpsPulse AI - Base VM Setup"
echo "=========================================="

# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install essentials
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    htop \
    tmux \
    nginx \
    certbot \
    python3-certbot-nginx \
    build-essential \
    libffi-dev \
    libssl-dev

# Install Docker (optional, for containerized deployments)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Create app directory
sudo mkdir -p /opt/opspulse
sudo chown $USER:$USER /opt/opspulse

# Clone repository
cd /opt/opspulse
git clone https://github.com/YOUR_USERNAME/OpsPulse.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

echo "Base setup complete!"
```

### 4.2 Environment Variables Setup

Create `/opt/opspulse/.env` on each VM:

```bash
# /opt/opspulse/.env

# API Keys
GOOGLE_API_KEY=your_google_api_key_here

# Kafka/Redpanda (already in code, but can override)
KAFKA_USERNAME=ashutosh
KAFKA_PASSWORD=768581

# Service URLs (update with actual internal IPs)
LOG_GENERATOR_URL=http://10.0.0.2:8000
RAG_SERVER_URL=http://10.0.0.3:5000
DEEPSEEK_URL=http://10.0.0.4:8080
DASHBOARD_API_URL=http://10.0.0.5:8001

# Deployment settings
DEBUG=false
ENVIRONMENT=production
```

---

## 5. Service Deployments

### 5.1 VM 1: Log Generator + Kafka Producer

SSH into `opspulse-logs`:

```bash
gcloud compute ssh opspulse-logs --zone=us-central1-a
```

#### Install Dependencies

```bash
cd /opt/opspulse
source venv/bin/activate

# Install log generator requirements
pip install -r logs_generator/requirements.txt
pip install -r Message_queue_kafka/requirements.txt
```

#### Create Systemd Service for Log Generator

```bash
sudo tee /etc/systemd/system/opspulse-logs.service << 'EOF'
[Unit]
Description=OpsPulse Log Generator API
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/opspulse
Environment="PATH=/opt/opspulse/venv/bin"
EnvironmentFile=/opt/opspulse/.env
ExecStart=/opt/opspulse/venv/bin/uvicorn logs_generator.server:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

#### Create Systemd Service for Kafka Producer

```bash
sudo tee /etc/systemd/system/opspulse-producer.service << 'EOF'
[Unit]
Description=OpsPulse Kafka Producer
After=network.target opspulse-logs.service
Requires=opspulse-logs.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/opspulse
Environment="PATH=/opt/opspulse/venv/bin"
EnvironmentFile=/opt/opspulse/.env
ExecStart=/opt/opspulse/venv/bin/python Message_queue_kafka/producer.py --continuous --server http://localhost:8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

#### Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable opspulse-logs opspulse-producer
sudo systemctl start opspulse-logs
sleep 5  # Wait for log generator to start
sudo systemctl start opspulse-producer

# Check status
sudo systemctl status opspulse-logs
sudo systemctl status opspulse-producer
```

---

### 5.2 VM 2: RAG Server

SSH into `opspulse-rag`:

```bash
gcloud compute ssh opspulse-rag --zone=us-central1-a
```

#### Install Dependencies

```bash
cd /opt/opspulse
source venv/bin/activate

# Install RAG requirements
pip install -r Rag/requirements.txt
```

#### Upload Runbook PDFs

```bash
# Create runbook directory
mkdir -p /opt/opspulse/run\ book

# Copy PDFs (from your local machine)
# gcloud compute scp ./run\ book/*.pdf opspulse-rag:/opt/opspulse/run\ book/ --zone=us-central1-a
```

#### Create Systemd Service for RAG Server

```bash
sudo tee /etc/systemd/system/opspulse-rag.service << 'EOF'
[Unit]
Description=OpsPulse RAG Server
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/opspulse
Environment="PATH=/opt/opspulse/venv/bin"
EnvironmentFile=/opt/opspulse/.env
ExecStart=/opt/opspulse/venv/bin/python -m Rag.server --host 0.0.0.0 --port 5000 --ingest
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
# RAG needs more time to start (PDF processing)
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOF
```

#### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable opspulse-rag
sudo systemctl start opspulse-rag

# Monitor startup (PDF ingestion takes time)
sudo journalctl -u opspulse-rag -f
```

---

### 5.3 VM 3: DeepSeek LLM

SSH into `opspulse-llm`:

```bash
gcloud compute ssh opspulse-llm --zone=us-central1-a
```

#### Option A: Self-hosted DeepSeek (Requires GPU)

```bash
# Install NVIDIA drivers (if using GPU)
sudo apt-get install -y nvidia-driver-535

# Install vLLM or text-generation-inference
pip install vllm

# Download and run DeepSeek model
# Note: DeepSeek-R1 is very large, consider using API instead
```

#### Option B: Use DeepSeek API (Recommended)

If using DeepSeek's hosted API, update the RAG config:

```bash
# /opt/opspulse/Rag/config.yaml
llm:
  model: "deepseek/deepseek-r1"
  api_base: "https://api.deepseek.com/v1"
  api_key: "YOUR_DEEPSEEK_API_KEY"
```

#### Option C: Use Compatible Local LLM

```bash
sudo tee /etc/systemd/system/opspulse-llm.service << 'EOF'
[Unit]
Description=OpsPulse LLM Server
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/opspulse
Environment="PATH=/opt/opspulse/venv/bin"
# Using Ollama as example
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

---

### 5.4 VM 4: Dashboard API + Pathway Consumer

SSH into `opspulse-dashboard`:

```bash
gcloud compute ssh opspulse-dashboard --zone=us-central1-a
```

#### Install Dependencies

```bash
cd /opt/opspulse
source venv/bin/activate

# Install all requirements
pip install -r backend/requirements.txt
pip install -r Message_queue_kafka/requirements.txt
pip install pathway
```

#### Create Systemd Service for Dashboard API

```bash
sudo tee /etc/systemd/system/opspulse-dashboard.service << 'EOF'
[Unit]
Description=OpsPulse Dashboard API
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/opspulse
Environment="PATH=/opt/opspulse/venv/bin"
EnvironmentFile=/opt/opspulse/.env
ExecStart=/opt/opspulse/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8001 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

#### Create Systemd Service for Pathway Consumer

```bash
sudo tee /etc/systemd/system/opspulse-pathway.service << 'EOF'
[Unit]
Description=OpsPulse Pathway Consumer
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/opspulse
Environment="PATH=/opt/opspulse/venv/bin"
EnvironmentFile=/opt/opspulse/.env
ExecStart=/opt/opspulse/venv/bin/python Message_queue_kafka/pathway_consumer.py --rag-url http://RAG_SERVER_IP:5000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

#### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable opspulse-dashboard opspulse-pathway
sudo systemctl start opspulse-dashboard opspulse-pathway

# Check status
sudo systemctl status opspulse-dashboard
sudo systemctl status opspulse-pathway
```

---

## 6. Nginx Reverse Proxy

### 6.1 Dashboard API Nginx Config

On `opspulse-dashboard` VM:

```bash
sudo tee /etc/nginx/sites-available/opspulse-api << 'EOF'
upstream dashboard_api {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name api.opspulse.ai;  # Or your domain/IP

    # Increase timeouts for WebSocket
    proxy_connect_timeout 7d;
    proxy_send_timeout 7d;
    proxy_read_timeout 7d;

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
    }

    # Health check endpoint
    location /health {
        proxy_pass http://dashboard_api/health;
        proxy_http_version 1.1;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/opspulse-api /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 6.2 Log Generator Nginx Config

On `opspulse-logs` VM:

```bash
sudo tee /etc/nginx/sites-available/opspulse-logs << 'EOF'
upstream log_generator {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name logs.opspulse.ai;

    location / {
        proxy_pass http://log_generator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://log_generator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/opspulse-logs /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 7. SSL/TLS Configuration

### 7.1 Using Let's Encrypt (Recommended)

```bash
# On each public-facing VM
sudo certbot --nginx -d your-subdomain.opspulse.ai

# Auto-renewal is configured automatically
# Test renewal
sudo certbot renew --dry-run
```

### 7.2 Using GCP-Managed SSL

If using Google Cloud Load Balancer:

```bash
# Create SSL certificate
gcloud compute ssl-certificates create opspulse-cert \
    --domains=api.opspulse.ai,logs.opspulse.ai

# Attach to load balancer (if using)
```

---

## 8. Firewall Rules

### 8.1 Production Firewall Configuration

```bash
# Remove overly permissive rules
gcloud compute firewall-rules delete opspulse-apps

# Create specific rules
# Dashboard API - public
gcloud compute firewall-rules create opspulse-dashboard-public \
    --network=opspulse-vpc \
    --allow=tcp:443,tcp:80 \
    --target-tags=opspulse-dashboard \
    --source-ranges=0.0.0.0/0

# Log Generator - restricted (only from known IPs)
gcloud compute firewall-rules create opspulse-logs-restricted \
    --network=opspulse-vpc \
    --allow=tcp:443,tcp:80 \
    --target-tags=opspulse-logs \
    --source-ranges=YOUR_OFFICE_IP/32,DASHBOARD_IP/32

# Internal services - only VPC
gcloud compute firewall-rules create opspulse-internal-services \
    --network=opspulse-vpc \
    --allow=tcp:5000,tcp:8080 \
    --target-tags=opspulse-rag,opspulse-llm \
    --source-ranges=10.0.0.0/24
```

---

## 9. Monitoring & Logging

### 9.1 GCP Cloud Monitoring

```bash
# Install monitoring agent on all VMs
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

### 9.2 Custom Metrics Dashboard

Create a monitoring dashboard in GCP Console:

1. Go to **Monitoring > Dashboards**
2. Create new dashboard
3. Add widgets for:
   - VM CPU/Memory usage
   - Network traffic
   - Custom metrics from `/api/system/metrics`

### 9.3 Log Collection

Configure ops-agent for application logs:

```bash
sudo tee /etc/google-cloud-ops-agent/config.yaml << 'EOF'
logging:
  receivers:
    opspulse_logs:
      type: files
      include_paths:
        - /var/log/opspulse/*.log
      record_log_file_path: true
    journald:
      type: systemd_journald
      units:
        - opspulse-logs
        - opspulse-producer
        - opspulse-rag
        - opspulse-dashboard
        - opspulse-pathway
  service:
    pipelines:
      opspulse:
        receivers:
          - opspulse_logs
          - journald
EOF

sudo systemctl restart google-cloud-ops-agent
```

### 9.4 Alerting Policies

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
    --display-name="OpsPulse High Error Rate" \
    --condition-display-name="Error rate > 10%" \
    --condition-filter='resource.type="gce_instance" AND metric.type="custom.googleapis.com/opspulse/error_rate"' \
    --condition-threshold-value=0.1 \
    --condition-threshold-comparison=COMPARISON_GT \
    --notification-channels=YOUR_CHANNEL_ID
```

---

## 10. Maintenance & Troubleshooting

### 10.1 Useful Commands

```bash
# View service logs
sudo journalctl -u opspulse-dashboard -f
sudo journalctl -u opspulse-pathway -f --since "10 minutes ago"

# Restart services
sudo systemctl restart opspulse-dashboard
sudo systemctl restart opspulse-pathway

# Check all OpsPulse services
sudo systemctl list-units 'opspulse-*'

# View resource usage
htop
df -h
free -m

# Test API health
curl http://localhost:8001/health
curl http://localhost:8001/api/system/health
```

### 10.2 Common Issues

#### Issue: RAG Server Won't Start

```bash
# Check logs
sudo journalctl -u opspulse-rag -n 100

# Common fix: Memory issues
# Increase VM size or adjust chunk size in config.yaml

# Verify PDF files exist
ls -la /opt/opspulse/run\ book/
```

#### Issue: Kafka Connection Failed

```bash
# Test Kafka connectivity
python3 << 'EOF'
from confluent_kafka import Consumer
conf = {
    'bootstrap.servers': 'your-kafka-server:9092',
    'security.protocol': 'SASL_SSL',
    'sasl.mechanisms': 'SCRAM-SHA-256',
    'sasl.username': 'your-username',
    'sasl.password': 'your-password',
    'group.id': 'test'
}
c = Consumer(conf)
print(c.list_topics())
c.close()
EOF
```

#### Issue: WebSocket Connection Drops

```bash
# Check Nginx timeout settings
sudo nginx -T | grep timeout

# Increase proxy timeouts
proxy_read_timeout 86400;
proxy_send_timeout 86400;
```

### 10.3 Backup & Recovery

```bash
# Backup ChromaDB data
tar -czf chromadb_backup_$(date +%Y%m%d).tar.gz /opt/opspulse/chromadb/

# Backup configuration
tar -czf config_backup_$(date +%Y%m%d).tar.gz /opt/opspulse/.env /opt/opspulse/*/config.yaml

# Copy to GCS
gsutil cp *_backup_*.tar.gz gs://your-backup-bucket/opspulse/
```

### 10.4 Updates & Deployments

```bash
# Update code from git
cd /opt/opspulse
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r backend/requirements.txt

# Restart services
sudo systemctl restart opspulse-dashboard opspulse-pathway

# Zero-downtime deployment (if using multiple instances)
# Use rolling restarts with health checks
```

---

## 📋 Quick Reference

### Service URLs (Internal)

| Service | URL |
|---------|-----|
| Log Generator | `http://10.0.0.2:8000` |
| RAG Server | `http://10.0.0.3:5000` |
| DeepSeek LLM | `http://10.0.0.4:8080` |
| Dashboard API | `http://10.0.0.5:8001` |

### Service URLs (External)

| Service | URL |
|---------|-----|
| Dashboard API | `https://api.opspulse.ai` |
| Log Generator | `https://logs.opspulse.ai` |
| API Docs | `https://api.opspulse.ai/docs` |
| WebSocket | `wss://api.opspulse.ai/ws/live` |

### Systemd Commands

```bash
# Start all services
sudo systemctl start opspulse-{logs,producer,rag,dashboard,pathway}

# Stop all services
sudo systemctl stop opspulse-{logs,producer,rag,dashboard,pathway}

# Restart all services
sudo systemctl restart opspulse-{logs,producer,rag,dashboard,pathway}

# Check status
sudo systemctl status opspulse-*
```

---

## 🎉 Post-Deployment Checklist

- [ ] All VMs created and running
- [ ] Firewall rules configured
- [ ] All services started and healthy
- [ ] Nginx configured and SSL enabled
- [ ] Kafka connectivity verified
- [ ] RAG server indexed PDFs
- [ ] Dashboard API accessible
- [ ] WebSocket connections working
- [ ] Monitoring dashboards set up
- [ ] Alerting policies configured
- [ ] Backup procedures documented
- [ ] Team access configured

---

**Congratulations! Your OpsPulse AI system is now deployed on GCP! 🚀**
