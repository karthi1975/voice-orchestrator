# Digital Ocean Multi-Tenant Deployment Guide

Complete guide for deploying Voice Orchestrator with PostgreSQL multi-tenant support on Digital Ocean.

## Prerequisites

- Digital Ocean droplet (Ubuntu 22.04)
- SSH access configured
- Domain/IP: `167.99.168.14`
- SSH key: `~/.ssh/digitalocean_healthedu`

## Quick Deployment

### Option 1: One-Command Deployment (Recommended)

```bash
./deploy-to-digitalocean-multitenant.sh
```

This script will:
1. ✅ Install Docker & Docker Compose
2. ✅ Clone/update repository
3. ✅ Setup PostgreSQL database
4. ✅ Run migrations
5. ✅ Start all services
6. ✅ Create default test user/home
7. ✅ Verify health checks

**Duration:** ~5-10 minutes

---

## Manual Deployment

If you prefer manual deployment or need to troubleshoot:

### Step 1: SSH to Server

```bash
ssh -i ~/.ssh/digitalocean_healthedu root@167.99.168.14
```

### Step 2: Install Dependencies

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Git & PostgreSQL client
apt-get update
apt-get install -y git postgresql-client curl
```

### Step 3: Clone Repository

```bash
mkdir -p /opt/voice-orchestrator
cd /opt/voice-orchestrator
git clone https://github.com/karthi1975/voice-orchestrator.git .
```

### Step 4: Configure Environment

```bash
# Generate secure secret key
SECRET_KEY=$(openssl rand -hex 32)

# Create .env file
cat > .env << EOF
FLASK_ENV=production
DEBUG=false
TEST_MODE=false
SECRET_KEY=${SECRET_KEY}

PORT=6500
HOST=0.0.0.0

# Multi-Tenant Database
USE_DATABASE=true
DATABASE_URL=postgresql://voiceorch:voiceorch_password_2026@postgres:5432/voice_orchestrator

# Home Assistant (fallback)
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
EOF
```

### Step 5: Create Docker Compose File

```bash
cat > docker-compose.yml << 'EOF'
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
  app_logs:
EOF
```

### Step 6: Build and Deploy

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Wait for PostgreSQL
sleep 10

# Run migrations
docker-compose exec app alembic upgrade head

# Check status
docker-compose ps
```

### Step 7: Verify Deployment

```bash
# Check health
curl http://localhost:6500/health

# Check logs
docker-compose logs app

# Check database
docker-compose exec postgres psql -U voiceorch voice_orchestrator -c "\dt"
```

---

## Post-Deployment Setup

### Create First User

```bash
curl -X POST http://167.99.168.14:6500/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "becca",
    "full_name": "Becca Smith",
    "email": "becca@example.com"
  }'
```

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "becca",
  "full_name": "Becca Smith",
  "email": "becca@example.com",
  "is_active": true,
  "created_at": "2026-01-29T12:00:00"
}
```

### Register User's Home

```bash
# Save user_id from previous response
USER_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST http://167.99.168.14:6500/admin/homes \
  -H "Content-Type: application/json" \
  -d "{
    \"home_id\": \"becca_main\",
    \"user_id\": \"${USER_ID}\",
    \"name\": \"Becca's Main House\",
    \"ha_url\": \"https://becca-ha.homeadapt.us\",
    \"ha_webhook_id\": \"voice_auth_scene\"
  }"
```

### Verify Setup

```bash
# List all users
curl http://167.99.168.14:6500/admin/users | jq

# List all homes
curl http://167.99.168.14:6500/admin/homes | jq

# List specific user's homes
curl http://167.99.168.14:6500/admin/users/${USER_ID}/homes | jq
```

---

## Operations

### View Logs

```bash
# Application logs
docker-compose logs -f app

# Database logs
docker-compose logs -f postgres

# Last 50 lines
docker-compose logs --tail 50 app
```

### Restart Services

```bash
# Restart application only
docker-compose restart app

# Restart everything
docker-compose restart

# Full rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U voiceorch voice_orchestrator

# Run migrations
docker-compose exec app alembic upgrade head

# Check migration status
docker-compose exec app alembic current

# Backup database
docker-compose exec postgres pg_dump -U voiceorch voice_orchestrator > backup_$(date +%Y%m%d).sql

# Restore database
cat backup.sql | docker-compose exec -T postgres psql -U voiceorch voice_orchestrator
```

### Update Application

```bash
cd /opt/voice-orchestrator

# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build app
docker-compose up -d app

# Run new migrations if any
docker-compose exec app alembic upgrade head
```

---

## Monitoring

### Health Checks

```bash
# Application health
curl http://167.99.168.14:6500/health

# Database health
docker-compose exec postgres pg_isready -U voiceorch
```

### Performance Monitoring

```bash
# Container stats
docker stats voice-orchestrator voice-orchestrator-db

# Disk usage
docker system df

# View active connections
docker-compose exec postgres psql -U voiceorch voice_orchestrator -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check logs
docker-compose logs app

# Check environment
docker-compose exec app env | grep DATABASE_URL

# Verify database connection
docker-compose exec app python3 -c "import psycopg2; psycopg2.connect('postgresql://voiceorch:voiceorch_password_2026@postgres:5432/voice_orchestrator')"
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U voiceorch voice_orchestrator -c "SELECT 1;"
```

### Port Already in Use

```bash
# Find process using port 6500
lsof -i :6500

# Kill old process
docker stop voice-orchestrator
docker rm voice-orchestrator
```

### Migration Failures

```bash
# Check migration status
docker-compose exec app alembic current

# View migration history
docker-compose exec app alembic history

# Downgrade one version
docker-compose exec app alembic downgrade -1

# Upgrade to latest
docker-compose exec app alembic upgrade head
```

---

## Security Considerations

### Change Default Passwords

1. Update PostgreSQL password in `.env`:
   ```bash
   DATABASE_URL=postgresql://voiceorch:YOUR_SECURE_PASSWORD@postgres:5432/voice_orchestrator
   ```

2. Update in `docker-compose.yml`:
   ```yaml
   environment:
     POSTGRES_PASSWORD: YOUR_SECURE_PASSWORD
   ```

3. Restart services:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Firewall Rules

```bash
# Allow only necessary ports
ufw allow 22/tcp   # SSH
ufw allow 6500/tcp # Application
ufw enable
```

### SSL/TLS (Recommended)

For production, use a reverse proxy with SSL:

```bash
# Install Nginx
apt-get install -y nginx certbot python3-certbot-nginx

# Configure Nginx
cat > /etc/nginx/sites-available/voice-orchestrator << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:6500;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/voice-orchestrator /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# Get SSL certificate
certbot --nginx -d your-domain.com
```

---

## Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/admin/users` | GET, POST | User management |
| `/admin/users/{id}` | GET, PUT, DELETE | User operations |
| `/admin/homes` | GET, POST | Home management |
| `/admin/homes/{id}` | GET, PUT, DELETE | Home operations |
| `/admin/users/{id}/homes` | GET | User's homes |
| `/futureproofhome/v2/auth/request` | POST | Request challenge |
| `/futureproofhome/v2/auth/validate` | POST | Validate response |
| `/alexa/v2` | POST | Alexa webhook |

---

## Backup Strategy

### Automated Backups

```bash
# Create backup script
cat > /opt/voice-orchestrator/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/opt/backups/voice-orchestrator
mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup database
docker-compose exec -T postgres pg_dump -U voiceorch voice_orchestrator \
  | gzip > $BACKUP_DIR/db_$TIMESTAMP.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete
EOF

chmod +x /opt/voice-orchestrator/backup.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /opt/voice-orchestrator/backup.sh" | crontab -
```

---

## Support

- **Documentation:** `docs/ADMIN_API.md`
- **GitHub:** https://github.com/karthi1975/voice-orchestrator
- **Logs:** `docker-compose logs -f app`

---

## Quick Commands Reference

```bash
# Deploy/Update
./deploy-to-digitalocean-multitenant.sh

# SSH to server
ssh -i ~/.ssh/digitalocean_healthedu root@167.99.168.14

# View logs
docker-compose logs -f app

# Restart
docker-compose restart app

# Database console
docker-compose exec postgres psql -U voiceorch voice_orchestrator

# Run migrations
docker-compose exec app alembic upgrade head

# Backup database
docker-compose exec postgres pg_dump -U voiceorch voice_orchestrator > backup.sql

# Health check
curl http://167.99.168.14:6500/health
```
