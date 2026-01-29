#!/bin/bash
# Deployment script for Digital Ocean

set -e

APP_DIR="/opt/voice-orchestrator"
DOCKER_IMAGE="voice-orchestrator:latest"

echo "=== Voice Orchestrator - Deployment ==="

# Navigate to app directory
cd $APP_DIR

# Pull latest code
echo "Updating code..."
git pull origin main

# Build Docker image
echo "Building Docker image..."
docker build -t $DOCKER_IMAGE -f docker/Dockerfile .

# Stop existing container
echo "Stopping existing container..."
docker stop voice-orchestrator || true
docker rm voice-orchestrator || true

# Run database migrations (if using database)
if grep -q "USE_DATABASE=true" .env; then
    echo "Running database migrations..."
    docker run --rm \
        --env-file .env \
        $DOCKER_IMAGE \
        python -m alembic upgrade head
fi

# Start new container
echo "Starting application container..."
docker run -d \
    --name voice-orchestrator \
    --restart unless-stopped \
    -p 127.0.0.1:6500:6500 \
    --env-file .env \
    --health-cmd="curl -f http://localhost:6500/health || exit 1" \
    --health-interval=30s \
    --health-timeout=3s \
    --health-retries=3 \
    $DOCKER_IMAGE

# Wait for health check
echo "Waiting for application to be healthy..."
sleep 10

# Check container status
if docker ps | grep -q voice-orchestrator; then
    echo "✓ Application deployed successfully"
    docker logs --tail 20 voice-orchestrator
else
    echo "✗ Deployment failed"
    docker logs voice-orchestrator
    exit 1
fi

# Reload Nginx
echo "Reloading Nginx..."
sudo nginx -t && sudo systemctl reload nginx

echo "=== Deployment Complete ==="
