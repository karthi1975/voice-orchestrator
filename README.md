# Unified Voice Authentication for Home Assistant

A Python voice authentication system that adds security to Home Assistant scene control via **Alexa** and **FutureProof Homes Satellite1** devices.

## Supported Voice Assistants

- **Amazon Alexa** - Cloud-based voice control via Alexa Skills
- **FutureProof Homes Satellite1** - 100% local, privacy-focused voice assistant ([Learn more](https://futureproofhomes.net/))

## How It Works

1. User: "Alexa, open home security"
2. Alexa: "Home security activated. Say night scene to begin."
3. User: "night scene"
4. Server generates random challenge (e.g., "ocean four")
5. Alexa: "Security check required. Please say: ocean four"
6. User: "ocean four"
7. Server validates voice response
8. If correct, triggers Home Assistant scene
9. Alexa: "Voice verified. Night scene activated."

## Features

- **Dual integration support**: Alexa and FutureProof Homes Satellite1
- **Unified authentication**: Both platforms share the same challenge-response logic
- **Isolated storage**: Separate namespaces for each integration
- **Random two-word challenge** generation (word + number)
- **Challenge expiry** (60 seconds)
- **Maximum attempt limiting** (3 attempts)
- **Spoken variation handling** ("4" → "four", "for" → "four")
- **Home Assistant webhook integration**
- **RESTful API** for FutureProof Homes
- **Simple web dashboard**
- **Health check endpoint**
- **TEST MODE** - Run without Home Assistant for testing
- **Comprehensive test suite** - 14+ automated tests

## FutureProof Homes Integration

In addition to Alexa, this system supports **FutureProof Homes Satellite1** devices - privacy-focused, local voice assistants that integrate with Home Assistant.

### Quick Start for FutureProof Homes

1. **Start the server**:
   ```bash
   ./start.sh
   ```

2. **Configure Home Assistant** with REST commands (see [home_assistant_config_futureproofhome.yaml](home_assistant_config_futureproofhome.yaml))

3. **Test the API**:
   ```bash
   curl -X POST http://localhost:6500/futureproofhome/auth/request \
     -H "Content-Type: application/json" \
     -d '{"home_id":"home_1","intent":"night_scene"}'
   ```

4. **Read the full guide**: [FUTUREPROOFHOME_INTEGRATION.md](FUTUREPROOFHOME_INTEGRATION.md)

### FutureProof Homes Endpoints

- `POST /futureproofhome/auth/request` - Request challenge
- `POST /futureproofhome/auth/verify` - Verify response
- `POST /futureproofhome/auth/cancel` - Cancel authentication
- `GET /futureproofhome/auth/status` - View pending challenges

### Alexa vs FutureProof Homes

| Feature | Alexa | FutureProof Homes |
|---------|-------|-------------------|
| Privacy | Cloud | 100% Local |
| Setup | Alexa Skills Kit | Home Assistant REST |
| Endpoint | `/alexa` | `/futureproofhome/*` |
| Storage | Session ID | Home ID |

## Testing Without Home Assistant

The system includes a **TEST_MODE** that lets you test the complete flow without having Home Assistant running:

1. **Enable TEST_MODE** (enabled by default in `config.py`):
   ```python
   TEST_MODE = True
   ```

2. **Run the test simulation**:
   ```bash
   python test_automation.py
   ```

3. When TEST_MODE is enabled, scene triggers will print to the console instead:
   ```
   ============================================================
   🏠 HOME ASSISTANT SCENE TRIGGER
   ============================================================
   Timestamp:    2026-01-06 18:27:19
   Scene:        Night Scene
   Scene ID:     night_scene
   Source:       Alexa Voice Authentication
   Status:       ✓ SUCCESS
   ============================================================
   ```

4. **Switch to production mode** when ready:
   ```python
   TEST_MODE = False  # Now it will actually call Home Assistant
   ```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Home Assistant

Edit `config.py` and set your Home Assistant URL:

```python
HA_URL = "http://YOUR_HOME_ASSISTANT_IP:8123"
HA_WEBHOOK_ID = "voice_auth_scene"
```

### 3. Create Home Assistant Automation

Add this automation to your Home Assistant `automations.yaml`:

```yaml
- alias: "Voice Auth Night Scene"
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

Or create via UI:
1. Settings → Automations & Scenes → Create Automation
2. Trigger: Webhook, ID: `voice_auth_scene`
3. Condition: Template `{{ trigger.json.scene == 'night_scene' }}`
4. Action: Call service `scene.turn_on` on your night scene

### 4. Start the Server

```bash
python server.py
```

Visit `http://localhost:5000` to see the dashboard.

### 5. Expose Server with ngrok

```bash
ngrok http 5000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### 6. Create Alexa Skill

1. Go to [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask)
2. Click "Create Skill"
3. Skill name: "Home Security"
4. Primary locale: English (US)
5. Choose "Custom" model
6. Choose "Provision your own" hosting
7. Click "Create skill"

### 7. Configure Skill Model

1. In the skill builder, click "JSON Editor" in the left sidebar
2. Delete all existing JSON
3. Copy contents of `alexa_skill_model.json` and paste
4. Click "Save Model"
5. Click "Build Model" (wait for build to complete)

### 8. Configure Endpoint

1. Click "Endpoint" in the left sidebar
2. Select "HTTPS"
3. Default Region: Enter `https://YOUR_NGROK_URL/alexa`
4. SSL Certificate Type: "My development endpoint is a sub-domain of a domain that has a wildcard certificate from a certificate authority"
5. Click "Save Endpoints"

### 9. Test the Skill

#### In Alexa Developer Console:

1. Click "Test" tab at the top
2. Enable testing: "Development"
3. Type or say: "open home security"
4. Follow the voice authentication flow

#### On Alexa Device:

1. "Alexa, open home security"
2. "night scene"
3. Repeat the challenge phrase
4. Scene activates if successful

## Example Conversation

```
User: "Alexa, open home security"
Alexa: "Home security activated. Say night scene to begin."

User: "night scene"
Alexa: "Security check required. Please say: mountain seven"

User: "mountain seven"
Alexa: "Voice verified. Night scene activated."
```

## Project Structure

```
.
├── config.py              # Configuration constants
├── challenge.py           # Challenge generation and validation
├── home_assistant.py      # Home Assistant webhook integration
├── server.py              # Flask server and Alexa handlers
├── alexa_skill_model.json # Alexa skill interaction model
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Configuration Options

Edit `config.py` to customize:

```python
# Challenge words and numbers
WORDS = ["apple", "banana", "dolphin", ...]
NUMBERS = ["one", "two", "three", ...]

# Security settings
CHALLENGE_EXPIRY_SECONDS = 60  # Challenge timeout
MAX_ATTEMPTS = 3               # Maximum validation attempts

# Home Assistant
HA_URL = "http://homeassistant.local:8123"
HA_WEBHOOK_ID = "voice_auth_scene"

# Server
PORT = 5000
DEBUG = True
```

## API Endpoints

### GET /
Dashboard page with status and instructions

### POST /alexa
Alexa skill webhook endpoint

### GET /health
Health check endpoint
```json
{
  "status": "healthy",
  "home_assistant": {
    "connected": true,
    "message": "Connected to Home Assistant: OK"
  }
}
```

## Adding More Scenes

To add more scenes (e.g., "morning scene"):

1. **Update server.py** - Add new intent handler:
```python
elif intent_name == 'MorningSceneIntent':
    return handle_morning_scene_intent(session_id)

def handle_morning_scene_intent(session_id):
    challenge = generate_challenge()
    store_challenge(session_id, challenge)
    speech = f"Security check required. Please say: {challenge}"
    return build_response(speech, should_end_session=False)
```

2. **Update alexa_skill_model.json** - Add new intent:
```json
{
  "name": "MorningSceneIntent",
  "slots": [],
  "samples": [
    "morning scene",
    "activate morning scene",
    "good morning",
    "morning mode"
  ]
}
```

3. **Create Home Assistant automation** for the new scene

4. Rebuild Alexa skill model in developer console

## Security Considerations

- This is a basic voice authentication system for convenience
- Not suitable for high-security scenarios
- Challenge is transmitted in clear text over HTTPS
- In-memory storage clears on restart
- For production, consider:
  - Database storage for challenges
  - Voice biometric authentication
  - Rate limiting
  - Audit logging
  - Multi-factor authentication

## Troubleshooting

### Server won't start
- Check if port 5000 is already in use
- Try changing PORT in config.py

### Home Assistant not responding
- Verify HA_URL in config.py
- Check Home Assistant is running
- Verify webhook automation is configured
- Check firewall settings

### Alexa skill not working
- Verify ngrok is running and URL is current
- Check Alexa endpoint URL is correct
- Look at CloudWatch logs in Alexa console
- Test endpoint with /health route

### Challenge validation failing
- Check server logs for the spoken response
- Verify normalization is working correctly
- Try speaking more clearly
- Check challenge hasn't expired

## Development

Run in debug mode to see detailed logs:

```bash
python server.py
```

Logs show:
- Incoming Alexa requests
- Challenge generation and validation
- Home Assistant communication
- Errors and exceptions

## License

MIT License - feel free to modify and use for your projects.

## Contributing

Contributions welcome! Areas for improvement:
- Voice biometric authentication
- Support for more Home Assistant services
- Multi-user support
- Database persistence
- Web UI for configuration
- Additional security features
