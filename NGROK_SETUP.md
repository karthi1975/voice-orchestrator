# ngrok Setup Guide for macOS

## Install ngrok

### Option 1: Using Homebrew (Recommended)
```bash
brew install ngrok/ngrok/ngrok
```

### Option 2: Manual Download
1. Visit https://ngrok.com/download
2. Download the macOS version
3. Unzip and move to /usr/local/bin:
   ```bash
   unzip ~/Downloads/ngrok-v3-stable-darwin-amd64.zip
   sudo mv ngrok /usr/local/bin/
   ```

## Setup ngrok Account (Free)

1. Sign up at https://dashboard.ngrok.com/signup
2. Get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken
3. Configure ngrok:
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN
   ```

## Run ngrok

Your server is running on port **6500**, so start ngrok:

```bash
ngrok http 6500
```

You should see output like:
```
ngrok

Session Status                online
Account                       your@email.com
Version                       3.x.x
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123def.ngrok-free.app -> http://localhost:6500

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

## Important URLs

Once ngrok is running, you'll get:

1. **Public HTTPS URL**: `https://abc123def.ngrok-free.app`
   - This is what you'll use for Alexa
   - Changes each time you restart ngrok (unless you have a paid plan)

2. **Web Interface**: `http://127.0.0.1:4040`
   - Monitor requests in real-time
   - See request/response details
   - Very helpful for debugging

## Configure Alexa Skill

1. Copy your ngrok HTTPS URL (e.g., `https://abc123def.ngrok-free.app`)

2. In Alexa Developer Console:
   - Go to your skill
   - Click "Endpoint" in left sidebar
   - Select "HTTPS"
   - Paste: `https://abc123def.ngrok-free.app/alexa`
   - SSL Certificate: Select "My development endpoint is a sub-domain..."
   - Save Endpoints

3. Test in Alexa Developer Console:
   - Click "Test" tab
   - Enable testing: "Development"
   - Type: "open home security"

## Testing Your Setup

### 1. Check Dashboard
Visit your server: http://localhost:6500

### 2. Check Health Endpoint
```bash
curl http://localhost:6500/health
```

### 3. Check ngrok is Working
```bash
curl https://YOUR-NGROK-URL.ngrok-free.app/health
```

### 4. Monitor Requests
Open ngrok web interface: http://127.0.0.1:4040

### 5. Test Alexa Endpoint
In Alexa Developer Console Test tab:
```
Type: "open home security"
Expected: "Home security activated. Say night scene to begin."
```

## Useful ngrok Commands

### Basic HTTP tunnel
```bash
ngrok http 6500
```

### With custom subdomain (requires paid plan)
```bash
ngrok http 6500 --subdomain=my-alexa-server
```

### With request inspection
```bash
ngrok http 6500 --inspect=true
```

### Check ngrok version
```bash
ngrok version
```

### View ngrok config
```bash
ngrok config check
```

## Troubleshooting

### ngrok: command not found
- Make sure ngrok is in your PATH
- Try: `which ngrok`
- Reinstall using Homebrew or add to PATH

### Port already in use
- Your server is on port 6500, so use: `ngrok http 6500`
- Check server is running: `lsof -i :6500`

### Alexa can't reach endpoint
1. Verify ngrok is running
2. Check ngrok URL is correct in Alexa console
3. Ensure URL ends with `/alexa`
4. Check ngrok web interface for errors
5. Verify server is responding: `curl YOUR_NGROK_URL/health`

### Connection closed errors
- Free ngrok URLs timeout after inactivity
- Just restart ngrok if this happens
- Consider paid plan for persistent URLs

### SSL Certificate errors
- Always select "My development endpoint is a sub-domain..."
- ngrok provides valid SSL certificates automatically

## Current Setup

- **Server Port**: 6500
- **Server URL**: http://localhost:6500 or http://192.168.1.231:6500
- **Alexa Endpoint Path**: `/alexa`
- **Full Alexa URL**: `https://YOUR-NGROK-URL.ngrok-free.app/alexa`

## Keeping ngrok Running

### Option 1: Keep Terminal Open
Just leave the ngrok terminal window open while testing

### Option 2: Run in Background
```bash
ngrok http 6500 > /dev/null &
```

### Option 3: Use tmux or screen
```bash
# Install tmux
brew install tmux

# Start tmux session
tmux new -s ngrok

# Run ngrok
ngrok http 6500

# Detach: Press Ctrl+B, then D
# Reattach: tmux attach -t ngrok
```

## Next Steps

1. ✅ Server is running on port 6500
2. ⬜ Install ngrok
3. ⬜ Sign up and get auth token
4. ⬜ Run `ngrok http 6500`
5. ⬜ Copy the HTTPS URL
6. ⬜ Configure Alexa skill endpoint
7. ⬜ Test with "open home security"

## Free vs Paid ngrok

**Free Plan:**
- ✅ HTTPS tunnels
- ✅ Random URLs
- ✅ 40 connections/minute
- ❌ URL changes on restart
- ❌ No custom domains

**Paid Plan ($8-10/month):**
- ✅ Reserved domains
- ✅ Custom subdomains
- ✅ More connections
- ✅ Static URLs
- ✅ Better for development

For testing, the free plan works great!
