#!/bin/bash
# Setup script for OpsPulse.ai Log Generator on GCP VM (Ubuntu)

set -e

echo "Updating system packages..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git

# Create a virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r logs_generator/requirements.txt

# Configure the log generator for continuous streaming
echo "Configuring log generator..."
# No specific config changes needed for server mode as it uses defaults
# but we ensure the output directory exists
mkdir -p output

# Setup systemd service
echo "Setting up systemd service..."
sudo cp deployment/opspulse-logs.service /etc/systemd/system/opspulse-logs.service
sudo systemctl daemon-reload
sudo systemctl enable opspulse-logs
sudo systemctl start opspulse-logs

echo "Deployment complete! The API is now running on port 8000."
echo "You can stream logs from: http://<VM_IP>:8000/api/stream"
echo "Or via WebSocket: ws://<VM_IP>:8000/ws/logs"
echo "IMPORTANT: Ensure port 8000 is open in your GCP Firewall settings."
