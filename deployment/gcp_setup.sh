#!/bin/bash
# ============================================================
# OpsPulse AI - GCP Infrastructure Setup Script
# ============================================================
# Run this script from your LOCAL machine with gcloud CLI installed
# Usage: chmod +x gcp_setup.sh && ./gcp_setup.sh
# ============================================================

set -e

echo "=========================================="
echo "☁️  OpsPulse AI - GCP Infrastructure Setup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# ==================== CONFIGURATION ====================
# Edit these values before running!

PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="us-central1"
ZONE="us-central1-a"
VPC_NAME="opspulse-vpc"
SUBNET_NAME="opspulse-subnet"
SUBNET_RANGE="10.0.0.0/24"

# VM Configurations
declare -A VM_CONFIG
VM_CONFIG[logs]="e2-small"
VM_CONFIG[rag]="e2-standard-4"
VM_CONFIG[llm]="e2-standard-2"
VM_CONFIG[dashboard]="e2-medium"

# Disk sizes (GB)
declare -A DISK_SIZE
DISK_SIZE[logs]="20"
DISK_SIZE[rag]="50"
DISK_SIZE[llm]="50"
DISK_SIZE[dashboard]="30"

# ==================== VALIDATION ====================

log_step "Validating configuration..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null 2>&1; then
    log_error "Not logged in to gcloud. Run: gcloud auth login"
    exit 1
fi

# Prompt for project ID if default
if [ "$PROJECT_ID" == "your-project-id" ]; then
    read -p "Enter your GCP Project ID: " PROJECT_ID
fi

log_info "Using project: $PROJECT_ID"
log_info "Region: $REGION"
log_info "Zone: $ZONE"

echo ""
read -p "Continue with this configuration? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Set project
gcloud config set project $PROJECT_ID

# ==================== ENABLE APIS ====================

log_step "Enabling required APIs..."
gcloud services enable compute.googleapis.com
gcloud services enable dns.googleapis.com
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com

# ==================== VPC NETWORK ====================

log_step "Creating VPC network..."

# Check if VPC exists
if gcloud compute networks describe $VPC_NAME --format="value(name)" 2>/dev/null; then
    log_warn "VPC $VPC_NAME already exists, skipping..."
else
    gcloud compute networks create $VPC_NAME \
        --subnet-mode=custom \
        --bgp-routing-mode=regional
    log_info "Created VPC: $VPC_NAME"
fi

# Create subnet
if gcloud compute networks subnets describe $SUBNET_NAME --region=$REGION --format="value(name)" 2>/dev/null; then
    log_warn "Subnet $SUBNET_NAME already exists, skipping..."
else
    gcloud compute networks subnets create $SUBNET_NAME \
        --network=$VPC_NAME \
        --region=$REGION \
        --range=$SUBNET_RANGE
    log_info "Created subnet: $SUBNET_NAME"
fi

# ==================== FIREWALL RULES ====================

log_step "Creating firewall rules..."

# Internal communication
if ! gcloud compute firewall-rules describe opspulse-internal --format="value(name)" 2>/dev/null; then
    gcloud compute firewall-rules create opspulse-internal \
        --network=$VPC_NAME \
        --allow=tcp:0-65535,udp:0-65535,icmp \
        --source-ranges=$SUBNET_RANGE \
        --description="Allow all internal traffic"
    log_info "Created firewall rule: opspulse-internal"
fi

# SSH access
if ! gcloud compute firewall-rules describe opspulse-ssh --format="value(name)" 2>/dev/null; then
    gcloud compute firewall-rules create opspulse-ssh \
        --network=$VPC_NAME \
        --allow=tcp:22 \
        --source-ranges=0.0.0.0/0 \
        --description="Allow SSH from anywhere"
    log_info "Created firewall rule: opspulse-ssh"
fi

# HTTP/HTTPS
if ! gcloud compute firewall-rules describe opspulse-http --format="value(name)" 2>/dev/null; then
    gcloud compute firewall-rules create opspulse-http \
        --network=$VPC_NAME \
        --allow=tcp:80,tcp:443 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=http-server,https-server \
        --description="Allow HTTP/HTTPS traffic"
    log_info "Created firewall rule: opspulse-http"
fi

# Application ports (for testing - restrict in production)
if ! gcloud compute firewall-rules describe opspulse-apps --format="value(name)" 2>/dev/null; then
    gcloud compute firewall-rules create opspulse-apps \
        --network=$VPC_NAME \
        --allow=tcp:8000,tcp:8001,tcp:5000,tcp:8080 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=opspulse-app \
        --description="Allow application ports (restrict in production)"
    log_info "Created firewall rule: opspulse-apps"
fi

# ==================== CREATE VMs ====================

log_step "Creating VM instances..."

# Function to create VM
create_vm() {
    local name=$1
    local machine_type=$2
    local disk_size=$3
    local tags=$4

    local vm_name="opspulse-$name"
    
    if gcloud compute instances describe $vm_name --zone=$ZONE --format="value(name)" 2>/dev/null; then
        log_warn "VM $vm_name already exists, skipping..."
        return
    fi

    log_info "Creating VM: $vm_name (${machine_type}, ${disk_size}GB)..."
    
    gcloud compute instances create $vm_name \
        --zone=$ZONE \
        --machine-type=$machine_type \
        --network=$VPC_NAME \
        --subnet=$SUBNET_NAME \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=${disk_size}GB \
        --boot-disk-type=pd-balanced \
        --tags=$tags \
        --metadata=startup-script='#!/bin/bash
apt-get update
apt-get install -y python3 python3-pip python3-venv git curl'
    
    log_info "Created VM: $vm_name"
}

# Create VMs
create_vm "logs" "${VM_CONFIG[logs]}" "${DISK_SIZE[logs]}" "opspulse-app,http-server"
create_vm "rag" "${VM_CONFIG[rag]}" "${DISK_SIZE[rag]}" "opspulse-app"
create_vm "llm" "${VM_CONFIG[llm]}" "${DISK_SIZE[llm]}" "opspulse-app"
create_vm "dashboard" "${VM_CONFIG[dashboard]}" "${DISK_SIZE[dashboard]}" "opspulse-app,http-server,https-server"

# ==================== RESERVE STATIC IPs ====================

log_step "Reserving static IP addresses..."

for vm in logs dashboard; do
    ip_name="opspulse-${vm}-ip"
    
    if gcloud compute addresses describe $ip_name --region=$REGION --format="value(name)" 2>/dev/null; then
        log_warn "IP $ip_name already reserved, skipping..."
    else
        gcloud compute addresses create $ip_name --region=$REGION
        log_info "Reserved IP: $ip_name"
    fi
done

# ==================== GET VM INFORMATION ====================

log_step "Gathering VM information..."

echo ""
echo "=========================================="
echo "📋 VM Information"
echo "=========================================="
echo ""

gcloud compute instances list --filter="name~opspulse" --format="table(name,zone,machineType,networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP,status)"

echo ""
echo "=========================================="
echo "🔑 SSH Commands"
echo "=========================================="
echo ""
for vm in logs rag llm dashboard; do
    echo "gcloud compute ssh opspulse-$vm --zone=$ZONE"
done

echo ""
echo "=========================================="
echo "📝 Next Steps"
echo "=========================================="
echo ""
echo "1. SSH into each VM and clone your repository:"
echo "   gcloud compute ssh opspulse-logs --zone=$ZONE"
echo "   git clone https://github.com/YOUR_USERNAME/OpsPulse.git /opt/opspulse"
echo ""
echo "2. Run the deployment scripts:"
echo "   - opspulse-logs:      ./deployment/deploy_logs_vm.sh"
echo "   - opspulse-rag:       ./deployment/deploy_rag_vm.sh"
echo "   - opspulse-dashboard: ./deployment/deploy_dashboard_vm.sh"
echo ""
echo "3. Update .env files with correct IPs"
echo ""
echo "4. Configure SSL certificates"
echo ""
echo "=========================================="
echo "✅ GCP Infrastructure Setup Complete!"
echo "=========================================="
