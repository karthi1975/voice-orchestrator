# Quick Start - Alexa Voice Authentication

## Current Status
✅ Server running on port 6500
✅ ngrok installed and configured
✅ TEST_MODE enabled (no Home Assistant needed)

## Run ngrok (Do This Now)

**Open a NEW terminal window** and run:

```bash
cd /Users/karthi/business/tetradapt/alexa_scene_automation
./START_NGROK.sh
```

Or simply:
```bash
ngrok http 6500
```

## What to Look For

You'll see output like this:
```
ngrok

Session Status                online
Forwarding                    https://abc123def.ngrok-free.app -> http://localhost:6500
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                              COPY THIS URL!
```

## Configure Alexa (One Time Setup)

1. **Copy your ngrok URL** (e.g., `https://abc123def.ngrok-free.app`)

2. **Go to Alexa Developer Console**: https://developer.amazon.com/alexa/console/ask

3. **Create or open your skill**:
   - Skill Name: "Home Security"
   - Model: Custom
   - Hosting: Provision your own

4. **Set Interaction Model**:
   - Click "JSON Editor"
   - Paste contents of `alexa_skill_model.json`
   - Save Model
   - Build Model

5. **Configure Endpoint**:
   - Click "Endpoint"
   - Select "HTTPS"
   - Default Region: `https://YOUR-NGROK-URL.ngrok-free.app/alexa`
   - SSL: "My development endpoint is a sub-domain..."
   - Save Endpoints

6. **Test**:
   - Click "Test" tab
   - Enable: "Development"
   - Type: "open home security"

## Test the Flow

### In Alexa Developer Console:

```
You: "open home security"
Alexa: "Home security activated. Say night scene to begin."

You: "night scene"
Alexa: "Security check required. Please say: [random phrase]"

You: [repeat the phrase]
Alexa: "Voice verified. Night scene activated."
```

### Check Server Console:

You should see the scene trigger printed:
```
============================================================
🏠 HOME ASSISTANT SCENE TRIGGER
============================================================
Timestamp:    2026-01-06 18:35:00
Scene:        Night Scene
Status:       ✓ SUCCESS
============================================================
```

## Monitor Requests

**ngrok Web Interface**: http://127.0.0.1:4040
- See all requests in real-time
- Inspect request/response details
- Debug Alexa communication

## Common Issues

### "I can't reach the skill"
- ✅ Check ngrok is running
- ✅ Check server is running on port 6500
- ✅ Verify endpoint URL ends with `/alexa`
- ✅ Make sure you're using HTTPS (not HTTP)

### "The endpoint doesn't respond"
```bash
# Test locally first
curl http://localhost:6500/health

# Test through ngrok
curl https://YOUR-NGROK-URL.ngrok-free.app/health
```

### ngrok URL changed
- Free ngrok URLs change when you restart
- Update Alexa endpoint with new URL
- Or upgrade to paid plan for static URLs

## Two Terminal Windows

**Terminal 1 - Server**:
```bash
cd /Users/karthi/business/tetradapt/alexa_scene_automation
source venv/bin/activate
python server.py
```

**Terminal 2 - ngrok**:
```bash
cd /Users/karthi/business/tetradapt/alexa_scene_automation
./START_NGROK.sh
```

## File Checklist

- ✅ `server.py` - Main server
- ✅ `config.py` - Configuration (PORT=6500, TEST_MODE=True)
- ✅ `alexa_skill_model.json` - Alexa interaction model
- ✅ `START_NGROK.sh` - ngrok launcher
- ✅ Virtual environment activated

## Ready to Go!

Your setup is complete. Just run ngrok and configure the Alexa skill endpoint!

---

**Need Help?**
- Full docs: `README.md`
- ngrok guide: `NGROK_SETUP.md`
- Test locally: `python test_automation.py`
