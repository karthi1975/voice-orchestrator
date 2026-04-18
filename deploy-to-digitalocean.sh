#!/bin/bash
# Local deployment script - Run this from your terminal
# It will SSH to your Digital Ocean server and deploy

set -e

echo "=== Voice Orchestrator - Digital Ocean Deployment ==="
echo ""
echo "This script will deploy to: 167.99.168.14"
echo "Press Ctrl+C to cancel, or press Enter to continue..."
read

# Deploy to server
ssh -i ~/.ssh/digitalocean_healthedu root@167.99.168.14 << 'ENDSSH'
set -e

echo ""
echo "=== Connected to Digital Ocean Server ==="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "→ Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    echo "✓ Docker installed"
else
    echo "✓ Docker already installed"
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "→ Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✓ Docker Compose installed"
else
    echo "✓ Docker Compose already installed"
fi

# Install essential packages
echo "→ Installing required packages..."
apt-get update -qq
apt-get install -y -qq git curl > /dev/null
echo "✓ Packages installed"

# Setup application directory
echo "→ Setting up application directory..."
mkdir -p /opt/voice-orchestrator
cd /opt/voice-orchestrator

# Clone or update repository
if [ -d ".git" ]; then
    echo "→ Updating repository..."
    git pull origin main
else
    echo "→ Cloning repository..."
    git clone https://github.com/karthi1975/voice-orchestrator.git .
fi
echo "✓ Repository ready"

# Create .env file
echo "→ Creating production configuration..."
cat > .env << 'ENVEOF'
# Flask Configuration
FLASK_ENV=production
DEBUG=false
TEST_MODE=false

# Security
SECRET_KEY=$(openssl rand -hex 32)

# Server
PORT=6500
HOST=0.0.0.0

# Home Assistant
HA_URL=http://homeassistant.local:8123
HA_WEBHOOK_ID=voice_auth_scene

# FutureProof Homes
FUTUREPROOFHOME_ENABLED=true
DEFAULT_HOME_ID=home_1
LOG_FPH_REQUESTS=false

# Database (in-memory mode)
USE_DATABASE=false

# Logging
LOG_LEVEL=INFO
LOG_REQUEST_BODY=false
LOG_RESPONSE_BODY=false

# VAPI integration (X-Vapi-Secret header enforcement)
VAPI_WEBHOOK_SECRET=41c9db6232f26141c5a601e459ed229af9cf1bb3d6a8553435384101016c1235

# HA Direct Dispatcher — single-webhook ingress, per-home REST API egress.
# HOME_CONFIGS_JSON holds per-home HA URL + long-lived bearer token. Kept
# empty in git; set on the droplet with: printf '\nHOME_CONFIGS_JSON=...\n' >> .env
HOME_CONFIGS_JSON={}

# Maps VAPI scene_name -> (HA service, entity suffix). Edit to add scenes.
SCENE_CATALOG_JSON={"night scene":{"service":"scene","entity":"night_mode"},"decorations on":{"service":"script","entity":"decorations_on"},"no decorations":{"service":"script","entity":"decorations_off"},"movie mode":{"service":"scene","entity":"movie"},"good morning":{"service":"scene","entity":"good_morning"}}

# Per-home overrides for scenes whose entity IDs diverge from the catalog.
HOME_SCENE_OVERRIDES_JSON={}
ENVEOF
echo "✓ Configuration created"

# Build Docker image
echo "→ Building Docker image..."
docker build -t voice-orchestrator:latest -f docker/Dockerfile . > /dev/null 2>&1
echo "✓ Docker image built"

# Stop existing container
echo "→ Stopping existing container (if any)..."
docker stop voice-orchestrator 2>/dev/null || true
docker rm voice-orchestrator 2>/dev/null || true
echo "✓ Old container removed"

# Start application
echo "→ Starting Voice Orchestrator..."
docker run -d \
    --name voice-orchestrator \
    --restart unless-stopped \
    -p 6500:6500 \
    --env-file .env \
    --health-cmd="curl -f http://localhost:6500/health || exit 1" \
    --health-interval=30s \
    --health-timeout=3s \
    --health-retries=3 \
    voice-orchestrator:latest > /dev/null

# Wait for startup
echo "→ Waiting for application startup..."
sleep 8

# Check status
echo ""
echo "=== Deployment Status ==="
docker ps --filter name=voice-orchestrator --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "→ Testing health endpoint..."
if curl -f -s http://localhost:6500/health > /dev/null; then
    echo "✓ Health check PASSED"
else
    echo "✗ Health check FAILED"
    echo "Logs:"
    docker logs --tail 20 voice-orchestrator
    exit 1
fi

echo ""
echo "=== Recent Logs ==="
docker logs --tail 10 voice-orchestrator

echo ""
echo "==================================================================="
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "==================================================================="
echo ""
echo "Application URL: http://167.99.168.14:6500"
echo ""
echo "Endpoints:"
echo "  • Health:         http://167.99.168.14:6500/health"
echo "  • Alexa (legacy): http://167.99.168.14:6500/alexa"
echo "  • Alexa (new):    http://167.99.168.14:6500/alexa/v2"
echo "  • FPH (legacy):   http://167.99.168.14:6500/futureproofhome"
echo "  • FPH (new):      http://167.99.168.14:6500/futureproofhome/v2"
echo ""
echo "Next steps:"
echo "  1. Update Alexa skill endpoint to /alexa/v2"
echo "  2. Test with: curl http://167.99.168.14:6500/health"
echo "  3. Monitor logs: ssh root@167.99.168.14 'docker logs -f voice-orchestrator'"
echo ""
echo "==================================================================="

ENDSSH

echo ""
echo "=== Local Verification ==="
echo "→ Testing from your machine..."
if curl -f -s http://167.99.168.14:6500/health > /dev/null; then
    echo "✓ Application is accessible from internet!"
    echo ""
    curl http://167.99.168.14:6500/health
else
    echo "⚠ Application not accessible yet (may need firewall rules)"
fi

echo ""
echo "Deployment complete!"
