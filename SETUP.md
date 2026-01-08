# Quick Setup Guide

## Virtual Environment Setup ✅

The virtual environment has been created and dependencies are installed!

### To activate the virtual environment:

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### To deactivate:
```bash
deactivate
```

## Running the Server

1. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Start the server:**
   ```bash
   python server.py
   ```

3. **Visit the dashboard:**
   Open browser to `http://localhost:5000`

## Testing

### Test Challenge System:
```bash
source venv/bin/activate
python test_challenge.py
```

### Test Complete Flow (without Home Assistant):
```bash
source venv/bin/activate
python test_automation.py
```

This will simulate the complete Alexa flow and show console output like:
```
🏠 HOME ASSISTANT SCENE TRIGGER
============================================================
Timestamp:    2026-01-06 18:27:19
Scene:        Night Scene
Status:       ✓ SUCCESS
============================================================
```

**Note:** TEST_MODE is enabled by default in `config.py`. Set `TEST_MODE = False` when you have Home Assistant running.

## Next Steps

1. **Update config.py** with your Home Assistant URL
2. **Setup ngrok** to expose the server:
   ```bash
   ngrok http 5000
   ```
3. **Configure Alexa Skill** (see README.md)
4. **Setup Home Assistant automation** (see home_assistant_config_example.yaml)

## Installed Packages

- Flask 3.0.0 - Web server framework
- Requests 2.31.0 - HTTP library for Home Assistant communication

## File Structure

```
alexa_scene_automation/
├── venv/                          # Virtual environment (DO NOT COMMIT)
├── config.py                      # Configuration
├── challenge.py                   # Challenge logic
├── home_assistant.py              # HA integration
├── server.py                      # Main Flask server
├── alexa_skill_model.json         # Alexa skill config
├── test_challenge.py              # Tests
├── home_assistant_config_example.yaml
├── requirements.txt
├── README.md                      # Full documentation
└── SETUP.md                       # This file
```

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run server
python server.py

# Run tests
python test_challenge.py

# Check health endpoint
curl http://localhost:5000/health

# Deactivate when done
deactivate
```

## Troubleshooting

**Port already in use:**
- Change `PORT` in config.py to a different port (e.g., 5001)

**ModuleNotFoundError:**
- Make sure virtual environment is activated
- Reinstall: `pip install -r requirements.txt`

**Home Assistant not reachable:**
- Update `HA_URL` in config.py
- Check Home Assistant is running
- Verify network connectivity
