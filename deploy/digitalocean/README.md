# Digital Ocean Deployment Guide

## Prerequisites

- Digital Ocean account
- Domain name (optional, for SSL)
- SSH access to droplet

## Infrastructure Setup

### Option 1: Managed Databases (Recommended)

Create managed PostgreSQL and Redis instances via Digital Ocean console.

**PostgreSQL:**
- Database → Create Database Cluster
- PostgreSQL 15
- Basic plan: $15/month
- Note connection string

**Redis (Optional):**
- Database → Create Database Cluster
- Redis
- Basic plan: $15/month

### Option 2: All-in-One Droplet

Run PostgreSQL and Redis alongside application in Docker Compose.

## Deployment Steps

### 1. Initial Server Setup

```bash
# SSH into droplet
ssh root@YOUR_DROPLET_IP

# Run setup script
curl -o setup.sh https://raw.githubusercontent.com/YOUR_REPO/main/deploy/digitalocean/setup.sh
chmod +x setup.sh
./setup.sh
```

### 2. Clone Repository

```bash
cd /opt
git clone https://github.com/YOUR_REPO/voice-orchestrator.git
cd voice-orchestrator
```

### 3. Configure Environment

```bash
# Copy example
cp .env.example .env

# Edit configuration
nano .env

# Required settings:
# - FLASK_ENV=production
# - SECRET_KEY=<generate with: openssl rand -hex 32>
# - DATABASE_URL=<your database URL>
# - HA_URL=<your Home Assistant URL>
```

### 4. Configure Nginx

```bash
# Copy config
sudo cp deploy/nginx/voice-orchestrator.conf /etc/nginx/sites-available/

# Update domain
sudo nano /etc/nginx/sites-available/voice-orchestrator.conf
# Replace "your-domain.com" with actual domain

# Enable site
sudo ln -s /etc/nginx/sites-available/voice-orchestrator.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Setup SSL (Optional)

```bash
sudo certbot --nginx -d your-domain.com
```

### 6. Deploy Application

```bash
chmod +x deploy/digitalocean/deploy.sh
./deploy/digitalocean/deploy.sh
```

### 7. Verify Deployment

```bash
# Check container
docker ps

# Check logs
docker logs voice-orchestrator

# Test health endpoint
curl http://localhost:6500/health
curl https://your-domain.com/health
```

## Monitoring

### View Logs

```bash
# Application logs
docker logs -f voice-orchestrator

# Nginx logs
sudo tail -f /var/log/nginx/voice-orchestrator-access.log
sudo tail -f /var/log/nginx/voice-orchestrator-error.log
```

### Container Stats

```bash
docker stats voice-orchestrator
```

## Updates

```bash
cd /opt/voice-orchestrator
./deploy/digitalocean/deploy.sh
```

## Troubleshooting

### Container Won't Start

```bash
docker logs voice-orchestrator
docker inspect voice-orchestrator
```

### Database Connection Issues

```bash
# Test connection
docker run --rm --env-file .env voice-orchestrator:latest \
    python -c "from app.config.settings import get_settings; print(get_settings('production').DATABASE_URL)"
```

### Nginx Issues

```bash
sudo nginx -t
sudo systemctl status nginx
sudo systemctl restart nginx
```

## Cost Estimate

- Droplet (2GB): $12/month
- PostgreSQL (Basic): $15/month
- **Total: $27/month**
