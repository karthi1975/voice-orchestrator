#!/bin/bash
# Multi-Tenant Deployment Script for Digital Ocean
# Deploys Voice Orchestrator with PostgreSQL support

set -e

echo "==================================================================="
echo "🚀 Voice Orchestrator - Multi-Tenant Digital Ocean Deployment"
echo "==================================================================="
echo ""
echo "This script will deploy to: 167.99.168.14"
echo "Mode: Multi-Tenant (PostgreSQL)"
echo ""
echo "Press Ctrl+C to cancel, or press Enter to continue..."
read

# Deploy to server
ssh -i ~/.ssh/digitalocean_healthedu root@167.99.168.14 << 'ENDSSH'
set -e

echo ""
echo "=== Connected to Digital Ocean Server ==="
echo ""

# Install Docker if needed
if ! command -v docker &> /dev/null; then
    echo "→ Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    echo "✓ Docker installed"
else
    echo "✓ Docker already installed"
fi

# Install Docker Compose if needed
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
apt-get install -y -qq git curl postgresql-client > /dev/null
echo "✓ Packages installed"

# Setup application directory
echo "→ Setting up application directory..."
mkdir -p /opt/voice-orchestrator
cd /opt/voice-orchestrator

# Clone or update repository
if [ -d ".git" ]; then
    echo "→ Updating repository..."
    git fetch origin
    git reset --hard origin/main
    git pull origin main
else
    echo "→ Cloning repository..."
    git clone https://github.com/karthi1975/voice-orchestrator.git .
fi
echo "✓ Repository ready"

# Generate secure secret key
SECRET_KEY=$(openssl rand -hex 32)

# Create production .env file
echo "→ Creating production configuration..."
cat > .env << ENVEOF
# Flask Configuration
FLASK_ENV=production
DEBUG=false
TEST_MODE=false

# Security
SECRET_KEY=${SECRET_KEY}

# Server
PORT=6500
HOST=0.0.0.0

# Multi-Tenant Database
USE_DATABASE=true
DATABASE_URL=postgresql://voiceorch:voiceorch_password_2026@postgres:5432/voice_orchestrator

# Home Assistant (Legacy - used for TEST_MODE or single-tenant fallback)
HA_URL=http://homeassistant.local:8123
HA_WEBHOOK_ID=voice_auth_scene

# FutureProof Homes
FUTUREPROOFHOME_ENABLED=true
DEFAULT_HOME_ID=home_1
LOG_FPH_REQUESTS=false

# Logging
LOG_LEVEL=INFO
LOG_REQUEST_BODY=false
LOG_RESPONSE_BODY=false

# Database Connection Pool
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
ENVEOF
echo "✓ Production configuration created"

# Create docker-compose.yml
echo "→ Creating Docker Compose configuration..."
cat > docker-compose.yml << 'COMPOSEEOF'
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: voice-orchestrator-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: voice_orchestrator
      POSTGRES_USER: voiceorch
      POSTGRES_PASSWORD: voiceorch_password_2026
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U voiceorch -d voice_orchestrator"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: voice-orchestrator
    restart: unless-stopped
    ports:
      - "6500:6500"
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6500/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    volumes:
      - app_logs:/app/logs

volumes:
  postgres_data:
    driver: local
  app_logs:
    driver: local
COMPOSEEOF
echo "✓ Docker Compose configuration created"

# Stop existing containers
echo "→ Stopping existing containers..."
docker-compose down 2>/dev/null || true
echo "✓ Old containers stopped"

# Build and start services
echo "→ Building Docker images..."
docker-compose build --no-cache > /dev/null 2>&1
echo "✓ Images built"

echo "→ Starting services (PostgreSQL + Application)..."
docker-compose up -d

# Wait for PostgreSQL to be ready
echo "→ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U voiceorch > /dev/null 2>&1; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    sleep 1
done

# Run database migrations
echo "→ Running database migrations..."
docker-compose exec -T app alembic upgrade head
echo "✓ Migrations completed"

# Wait for application startup
echo "→ Waiting for application startup..."
sleep 10

# Check status
echo ""
echo "=== Deployment Status ==="
docker-compose ps

echo ""
echo "→ Testing health endpoint..."
if curl -f -s http://localhost:6500/health > /dev/null; then
    echo "✓ Health check PASSED"
else
    echo "✗ Health check FAILED"
    echo "Application Logs:"
    docker-compose logs --tail 30 app
    echo ""
    echo "Database Logs:"
    docker-compose logs --tail 10 postgres
    exit 1
fi

# Create default user and home (optional)
echo ""
echo "→ Creating default test user..."
docker-compose exec -T app python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')

from app import create_app
app = create_app()

with app.app_context():
    try:
        from app.services.user_service import UserService
        from app.services.home_service import HomeService

        user_service = app.container.user_service
        home_service = app.container.home_service

        # Create default user
        try:
            user = user_service.create_user(
                username="default_user",
                full_name="Default User",
                email="admin@example.com"
            )
            print(f"✓ Default user created: {user.user_id}")

            # Create default home
            home = home_service.register_home(
                home_id="home_1",
                user_id=user.user_id,
                name="Default Home",
                ha_url="http://homeassistant.local:8123",
                ha_webhook_id="voice_auth_scene"
            )
            print(f"✓ Default home created: {home.home_id}")
        except Exception as e:
            print(f"ℹ Default user/home already exists: {str(e)}")
    except Exception as e:
        print(f"⚠ Could not create default data: {str(e)}")
PYEOF

echo ""
echo "=== Recent Application Logs ==="
docker-compose logs --tail 15 app

echo ""
echo "==================================================================="
echo "🎉 MULTI-TENANT DEPLOYMENT SUCCESSFUL!"
echo "==================================================================="
echo ""
echo "Application URL: http://167.99.168.14:6500"
echo ""
echo "Endpoints:"
echo "  • Health:         http://167.99.168.14:6500/health"
echo "  • Admin API:      http://167.99.168.14:6500/admin/*"
echo "  • Alexa:          http://167.99.168.14:6500/alexa/*"
echo "  • FPH:            http://167.99.168.14:6500/futureproofhome/*"
echo ""
echo "Admin API Examples:"
echo "  • List users:     curl http://167.99.168.14:6500/admin/users"
echo "  • List homes:     curl http://167.99.168.14:6500/admin/homes"
echo ""
echo "Database:"
echo "  • PostgreSQL:     localhost:5432"
echo "  • Database:       voice_orchestrator"
echo "  • User:           voiceorch"
echo ""
echo "Useful Commands:"
echo "  • View logs:      docker-compose logs -f app"
echo "  • View DB logs:   docker-compose logs -f postgres"
echo "  • Restart:        docker-compose restart app"
echo "  • Stop all:       docker-compose down"
echo "  • DB shell:       docker-compose exec postgres psql -U voiceorch voice_orchestrator"
echo "  • App shell:      docker-compose exec app /bin/bash"
echo ""
echo "Next Steps:"
echo "  1. Create users via Admin API (see docs/ADMIN_API.md)"
echo "  2. Register homes for each user"
echo "  3. Update FutureProof Homes to send home_id"
echo "  4. Monitor: docker-compose logs -f"
echo ""
echo "==================================================================="

ENDSSH

echo ""
echo "=== Local Verification ==="
echo "→ Testing from your machine..."

# Test health endpoint
if curl -f -s http://167.99.168.14:6500/health > /dev/null; then
    echo "✓ Application is accessible!"
    echo ""
    curl -s http://167.99.168.14:6500/health | python3 -m json.tool
else
    echo "⚠ Application not accessible yet"
fi

# Test admin endpoints
echo ""
echo "→ Testing Admin API..."
curl -s http://167.99.168.14:6500/admin/users | python3 -m json.tool 2>/dev/null || echo "Admin API: (empty or pending)"

echo ""
echo "==================================================================="
echo "✓ Multi-Tenant Deployment Complete!"
echo "==================================================================="
echo ""
echo "SSH to server: ssh -i ~/.ssh/digitalocean_healthedu root@167.99.168.14"
echo "View logs:     ssh -i ~/.ssh/digitalocean_healthedu root@167.99.168.14 'cd /opt/voice-orchestrator && docker-compose logs -f'"
echo ""
