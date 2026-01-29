#!/bin/bash
# Initial setup script for Digital Ocean droplet

set -e

echo "=== Voice Orchestrator - Digital Ocean Setup ==="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Nginx
echo "Installing Nginx..."
sudo apt-get install -y nginx

# Install certbot for SSL
echo "Installing Certbot..."
sudo apt-get install -y certbot python3-certbot-nginx

# Create application directory
echo "Creating application directory..."
sudo mkdir -p /opt/voice-orchestrator
sudo chown $USER:$USER /opt/voice-orchestrator

# Install PostgreSQL client (for migrations)
echo "Installing PostgreSQL client..."
sudo apt-get install -y postgresql-client

# Configure firewall
echo "Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "=== Setup Complete ==="
echo "Next steps:"
echo "1. Clone repository to /opt/voice-orchestrator"
echo "2. Create .env file with database credentials"
echo "3. Run deploy.sh"
