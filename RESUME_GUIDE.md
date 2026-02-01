# Voice Orchestrator - Quick Resume Guide

## 🚀 Deployment Status

**Production URL:** https://voiceorchestrator.homeadapt.us

**Server:** 167.99.168.14 (DigitalOcean - sfo2-01)

**Status:** ✅ Fully Deployed and Running

---

## 📋 Quick Health Check

### Check if everything is running:

```bash
# 1. SSH to server
ssh -i ~/.ssh/digitalocean_healthedu root@167.99.168.14

# 2. Check Docker containers
docker-compose ps

# Expected output:
# voice-orchestrator      Up (healthy)
# voice-orchestrator-db   Up (healthy)

# 3. Check application health
curl https://voiceorchestrator.homeadapt.us/health

# 4. Check logs (if needed)
docker-compose logs --tail 50 app
```

---

## 🔧 Common Operations

### Start/Stop Services

```bash
cd /opt/voice-orchestrator

# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart app only
docker-compose restart app

# View logs
docker-compose logs -f app

# Check status
docker-compose ps
```

### Update Application

```bash
cd /opt/voice-orchestrator

# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build --no-cache app
docker-compose up -d app

# Run migrations (if schema changed)
docker-compose exec app alembic upgrade head
```

### Database Operations

```bash
# Connect to database
docker-compose exec postgres psql -U voiceorch voice_orchestrator

# Run migrations
docker-compose exec app alembic upgrade head

# Check migration status
docker-compose exec app alembic current

# Backup database
docker-compose exec postgres pg_dump -U voiceorch voice_orchestrator > backup_$(date +%Y%m%d).sql
```

---

## 👥 User Management

### Current Users

**User:** Becca Farewell
- Email: wholelotoflife@gmail.com
- User ID: `e220e4ca-597a-4155-933a-ee633a29cc78`
- Home ID: `becca_farewell_beach`
- Home Assistant: https://ut-demo-beachhome.homeadapt.us

### Add New User

```bash
# 1. Create user JSON
cat > /tmp/new_user.json << 'EOF'
{
  "username": "username_here",
  "full_name": "Full Name Here",
  "email": "email@example.com"
}
EOF

# 2. Create user
curl -X POST https://voiceorchestrator.homeadapt.us/admin/users \
  -H "Content-Type: application/json" \
  -d @/tmp/new_user.json

# 3. Copy the user_id from response

# 4. Register home
cat > /tmp/new_home.json << 'EOF'
{
  "home_id": "unique_home_id",
  "user_id": "USER_ID_FROM_STEP_3",
  "name": "Home Name",
  "ha_url": "https://their-ha-url.com",
  "ha_webhook_id": "voice_auth_scene"
}
EOF

curl -X POST https://voiceorchestrator.homeadapt.us/admin/homes \
  -H "Content-Type: application/json" \
  -d @/tmp/new_home.json
```

### List Users and Homes

```bash
# List all users
curl https://voiceorchestrator.homeadapt.us/admin/users | python3 -m json.tool

# List all homes
curl https://voiceorchestrator.homeadapt.us/admin/homes | python3 -m json.tool

# Get specific user's homes
curl https://voiceorchestrator.homeadapt.us/admin/users/USER_ID/homes | python3 -m json.tool
```

---

## 🧪 Testing

### Quick Test - Complete Flow

```bash
# Test authentication flow
curl -X POST https://voiceorchestrator.homeadapt.us/futureproofhome/v2/auth/request \
  -H "Content-Type: application/json" \
  -d '{"home_id":"becca_farewell_beach","intent":"night_scene"}'

# Copy the challenge from response, then verify:
curl -X POST https://voiceorchestrator.homeadapt.us/futureproofhome/v2/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"home_id":"becca_farewell_beach","response":"CHALLENGE_HERE"}'
```

### Automated Test Script

```bash
# Save this as test_flow.sh
#!/bin/bash
echo "1. Requesting challenge..."
RESPONSE=$(curl -s -X POST https://voiceorchestrator.homeadapt.us/futureproofhome/v2/auth/request \
  -H "Content-Type: application/json" \
  -d '{"home_id":"becca_farewell_beach","intent":"night_scene"}')

echo "$RESPONSE" | python3 -m json.tool

CHALLENGE=$(echo $RESPONSE | grep -o '"challenge":"[^"]*"' | cut -d'"' -f4)
echo ""
echo "2. Challenge: $CHALLENGE"
echo ""
echo "3. Verifying..."
curl -s -X POST https://voiceorchestrator.homeadapt.us/futureproofhome/v2/auth/verify \
  -H "Content-Type: application/json" \
  -d "{\"home_id\":\"becca_farewell_beach\",\"response\":\"$CHALLENGE\"}" | python3 -m json.tool
```

---

## 📡 API Endpoints Reference

### Admin API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/users` | GET | List all users |
| `/admin/users` | POST | Create user |
| `/admin/users/{id}` | GET | Get user details |
| `/admin/users/{id}` | PUT | Update user |
| `/admin/users/{id}` | DELETE | Deactivate user |
| `/admin/homes` | GET | List all homes |
| `/admin/homes` | POST | Register home |
| `/admin/homes/{id}` | GET | Get home details |
| `/admin/homes/{id}` | PUT | Update home |
| `/admin/homes/{id}` | DELETE | Deactivate home |
| `/admin/users/{id}/homes` | GET | Get user's homes |

### FutureProof Homes API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/futureproofhome/v2/auth/request` | POST | Request challenge |
| `/futureproofhome/v2/auth/verify` | POST | Verify response |
| `/futureproofhome/v2/auth/cancel` | POST | Cancel auth |
| `/futureproofhome/v2/auth/status` | GET | Check status |

### Health & Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |

---

## 🔐 SSL Certificates

**Location:** `/etc/nginx/ssl/`

**Files:**
- `homeadapt.crt` - Cloudflare Origin Certificate
- `homeadapt.key` - Private key
- `origin_ca_rsa_root.crt` - CA certificate
- `dhparam.pem` - Diffie-Hellman parameters

**Renewal:** Cloudflare Origin Certificates don't expire until 2040.

---

## 🏗️ Architecture

### Components

```
┌──────────────────────────────────────────────────────────┐
│                      Cloudflare                          │
│  (SSL/TLS, CDN, DDoS Protection)                        │
└────────────────────┬─────────────────────────────────────┘
                     │ HTTPS
                     ↓
┌──────────────────────────────────────────────────────────┐
│               Nginx (Port 80/443)                        │
│  - Reverse Proxy                                         │
│  - SSL Termination                                       │
└────────────────────┬─────────────────────────────────────┘
                     │ HTTP (localhost:6500)
                     ↓
┌──────────────────────────────────────────────────────────┐
│        Voice Orchestrator (Flask App)                    │
│  - Multi-tenant routing                                  │
│  - Challenge generation/validation                       │
│  - Admin API                                             │
│  - FutureProof Homes API                                │
└────────────────────┬─────────────────────────────────────┘
                     │
         ┌───────────┴──────────┬────────────────────┐
         ↓                      ↓                    ↓
┌─────────────────┐   ┌──────────────────┐   ┌──────────────┐
│   PostgreSQL    │   │ Home Assistant 1 │   │Home Assistant│
│   (Database)    │   │  (Becca's Home)  │   │     N...     │
└─────────────────┘   └──────────────────┘   └──────────────┘
```

### Tech Stack

- **Frontend:** None (REST API only)
- **Backend:** Flask 3.0.0 (Python 3.11)
- **Database:** PostgreSQL 15
- **ORM:** SQLAlchemy 2.0.35
- **Migrations:** Alembic 1.13.0
- **Web Server:** Nginx
- **Container:** Docker + Docker Compose
- **SSL/CDN:** Cloudflare

---

## 🐛 Troubleshooting

### App won't start

```bash
# Check logs
docker-compose logs --tail 100 app

# Check database connection
docker-compose exec app python3 -c "from app import create_app; app = create_app(); print('OK')"

# Restart everything
docker-compose down
docker-compose up -d
```

### Database issues

```bash
# Check database is running
docker-compose ps postgres

# Check database connection
docker-compose exec postgres psql -U voiceorch voice_orchestrator -c "SELECT 1;"

# Check tables exist
docker-compose exec postgres psql -U voiceorch voice_orchestrator -c "\dt"
```

### Nginx issues

```bash
# Check Nginx config
nginx -t

# Check Nginx is running
systemctl status nginx

# Reload Nginx
systemctl reload nginx

# Check Nginx logs
tail -50 /var/log/nginx/error.log
```

### SSL/Cloudflare issues

```bash
# Test direct server (bypass Cloudflare)
curl http://167.99.168.14/health

# Test via Cloudflare
curl https://voiceorchestrator.homeadapt.us/health

# Check SSL certificates
ls -la /etc/nginx/ssl/
openssl x509 -in /etc/nginx/ssl/homeadapt.crt -text -noout
```

---

## 📞 Integration Setup

### Alexa Skills Kit

1. **Console:** https://developer.amazon.com/alexa/console/ask
2. **Endpoint:** `https://voiceorchestrator.homeadapt.us/alexa/v2`
3. **Skill Model:** See `alexa_skill_model.json`

### Home Assistant

**Webhook Automation:**

```yaml
- alias: "Voice Auth - Night Scene"
  trigger:
    - platform: webhook
      webhook_id: voice_auth_scene
  condition:
    - condition: template
      value_template: "{{ trigger.json.scene == 'night_scene' }}"
  action:
    - service: scene.turn_on
      target:
        entity_id: scene.night_mode
```

**Webhook URL:** `https://YOUR_HA_URL/api/webhook/voice_auth_scene`

---

## 📁 Important Files

### On Server (167.99.168.14)

```
/opt/voice-orchestrator/
├── docker-compose.yml          # Docker services config
├── .env                        # Environment variables
├── app/                        # Application code
├── migrations/                 # Database migrations
└── logs/                       # Application logs

/etc/nginx/
├── sites-available/voiceorchestrator
└── ssl/                        # SSL certificates
```

### Local Repository

```
alexa_scene_automation/
├── app/                        # Application code
├── migrations/                 # Database migrations
├── docker/                     # Dockerfile
├── docs/                       # Documentation
├── requirements.txt            # Python dependencies
├── server.py                   # Main entry point
├── RESUME_GUIDE.md            # This file
└── Architecture_Flow          # Architecture diagram
```

---

## 🚨 Emergency Contacts

**Server:** DigitalOcean - 167.99.168.14 (sfo2-01)
**Domain:** Cloudflare - homeadapt.us
**User Email:** wholelotoflife@gmail.com
**GitHub:** https://github.com/karthi1975/voice-orchestrator

---

## ✅ Quick Checklist

When resuming work:

- [ ] SSH to server: `ssh -i ~/.ssh/digitalocean_healthedu root@167.99.168.14`
- [ ] Check services: `docker-compose ps`
- [ ] Check health: `curl https://voiceorchestrator.homeadapt.us/health`
- [ ] Check logs if needed: `docker-compose logs --tail 50 app`
- [ ] Test authentication flow (see Testing section above)

---

## 📝 Notes

- Database credentials are in `/opt/voice-orchestrator/.env`
- SSL certificates don't expire until 2040
- Cloudflare is in "Full" SSL mode
- Nginx forwards port 80/443 → 6500
- PostgreSQL runs on localhost:5432 (not exposed externally)

---

**Last Updated:** 2026-01-30
**Deployment Status:** ✅ Production Ready
**Version:** 1.0.0 (Multi-tenant)
