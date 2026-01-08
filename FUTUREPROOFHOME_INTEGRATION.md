# FutureProof Homes Integration Guide

## Overview

This guide explains how to integrate **FutureProof Homes Satellite1** devices with the voice authentication system. FutureProof Homes provides privacy-focused, local voice assistants that work with Home Assistant.

### What is FutureProof Homes?

[FutureProof Homes](https://futureproofhomes.net/) manufactures open-source smart home voice assistant hardware. Their flagship product, the **Satellite1 Dev Kit** ($69.99), is a:
- **100% private, local voice assistant** (no cloud required)
- **Home Assistant-compatible device** with voice control
- **Multi-room audio** system with environmental sensors
- **Open-source** hardware with GPIO access

---

## Architecture

```
User speaks → Satellite1 Device
                    ↓
         Home Assistant (local)
                    ↓
    POST /futureproofhome/auth/request
                    ↓
         Orchestrator generates challenge
                    ↓
    Response: {"challenge": "ocean four"}
                    ↓
         Home Assistant → TTS via Satellite1
                    ↓
         User repeats: "ocean four"
                    ↓
         Satellite1 → Home Assistant
                    ↓
    POST /futureproofhome/auth/verify
                    ↓
         Orchestrator validates response
                    ↓
    Response: {"status": "approved", "intent": "night_scene"}
                    ↓
         Home Assistant executes scene
```

---

## Prerequisites

1. **Running Home Assistant** instance
2. **FutureProof Homes Satellite1** device configured
3. **This orchestrator server** running and accessible from Home Assistant
4. **Network access** between Home Assistant and orchestrator server

---

## Installation

### 1. Start the Orchestrator Server

```bash
cd /path/to/alexa_scene_automation
source venv/bin/activate
python server.py
```

Server will start on port 6500 (configurable in `config.py`).

### 2. Find Your Server IP Address

```bash
# On Mac/Linux
ipconfig getifaddr en0

# Or
ifconfig | grep "inet "
```

Example: `192.168.1.100`

### 3. Configure Home Assistant

See [home_assistant_config_futureproofhome.yaml](home_assistant_config_futureproofhome.yaml) for complete example.

---

## API Endpoints

### POST /futureproofhome/auth/request

Request a voice authentication challenge.

**Request:**
```json
{
  "home_id": "home_1",
  "intent": "night_scene"
}
```

**Response:**
```json
{
  "status": "challenge",
  "speech": "Security check. Please say: ocean four",
  "challenge": "ocean four"
}
```

**Example with curl:**
```bash
curl -X POST http://192.168.1.100:6500/futureproofhome/auth/request \
  -H "Content-Type: application/json" \
  -d '{"home_id":"home_1","intent":"night_scene"}'
```

---

### POST /futureproofhome/auth/verify

Verify the user's spoken response.

**Request:**
```json
{
  "home_id": "home_1",
  "response": "ocean four"
}
```

**Approved Response:**
```json
{
  "status": "approved",
  "speech": "Voice verified.",
  "intent": "night_scene"
}
```

**Denied Response:**
```json
{
  "status": "denied",
  "speech": "That didn't match. Try again.",
  "reason": "mismatch",
  "attempts_remaining": 2
}
```

**Denial Reasons:**
- `no_challenge` - No pending challenge found
- `expired` - Challenge has expired (60 seconds)
- `max_attempts` - Maximum attempts exceeded (3 attempts)
- `mismatch` - Response didn't match challenge

**Example with curl:**
```bash
curl -X POST http://192.168.1.100:6500/futureproofhome/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"home_id":"home_1","response":"ocean four"}'
```

---

### POST /futureproofhome/auth/cancel

Cancel a pending authentication.

**Request:**
```json
{
  "home_id": "home_1"
}
```

**Response:**
```json
{
  "status": "cancelled",
  "speech": "Security check cancelled."
}
```

---

### GET /futureproofhome/auth/status

Debug endpoint to view pending challenges.

**Response:**
```json
{
  "pending_challenges": {
    "home_1": {
      "intent": "night_scene",
      "attempts": 1,
      "elapsed_seconds": 15.2,
      "expired": false
    }
  },
  "config": {
    "expiry_seconds": 60,
    "max_attempts": 3
  },
  "total_pending": 1
}
```

---

## Home Assistant Configuration

### Step 1: Add REST Commands

Add to `configuration.yaml`:

```yaml
rest_command:
  fph_auth_request:
    url: "http://192.168.1.100:6500/futureproofhome/auth/request"
    method: POST
    content_type: "application/json"
    payload: '{"home_id": "{{ home_id }}", "intent": "{{ intent }}"}'

  fph_auth_verify:
    url: "http://192.168.1.100:6500/futureproofhome/auth/verify"
    method: POST
    content_type: "application/json"
    payload: '{"home_id": "{{ home_id }}", "response": "{{ response }}"}'

  fph_auth_cancel:
    url: "http://192.168.1.100:6500/futureproofhome/auth/cancel"
    method: POST
    content_type: "application/json"
    payload: '{"home_id": "{{ home_id }}"}'
```

Replace `192.168.1.100` with your server's IP address.

### Step 2: Add Input Helpers

```yaml
input_text:
  fph_voice_auth_state:
    name: FPH Voice Auth State
    initial: idle
    max: 50

  fph_voice_auth_challenge:
    name: FPH Voice Auth Challenge
    max: 100

  fph_voice_auth_pending_intent:
    name: FPH Pending Intent
    max: 50

  fph_voice_auth_home_id:
    name: FPH Home ID
    initial: home_1
    max: 50

input_boolean:
  fph_voice_auth_enabled:
    name: Enable FutureProof Homes Voice Auth
    initial: true

timer:
  fph_voice_auth_timeout:
    duration: "00:01:00"
```

### Step 3: Create Scripts

```yaml
script:
  fph_request_night_scene_auth:
    sequence:
      - service: input_text.set_value
        target:
          entity_id: input_text.fph_voice_auth_state
        data:
          value: "requesting"

      - service: rest_command.fph_auth_request
        data:
          home_id: "{{ states('input_text.fph_voice_auth_home_id') }}"
          intent: "night_scene"
        response_variable: auth_response

      - service: input_text.set_value
        target:
          entity_id: input_text.fph_voice_auth_challenge
        data:
          value: "{{ auth_response.content.challenge }}"

      - service: input_text.set_value
        target:
          entity_id: input_text.fph_voice_auth_pending_intent
        data:
          value: "night_scene"

      - service: input_text.set_value
        target:
          entity_id: input_text.fph_voice_auth_state
        data:
          value: "waiting_for_response"

      - service: timer.start
        target:
          entity_id: timer.fph_voice_auth_timeout

      - service: tts.speak
        target:
          entity_id: media_player.satellite1_living_room
        data:
          message: "{{ auth_response.content.speech }}"

  fph_verify_voice_response:
    sequence:
      - service: input_text.set_value
        target:
          entity_id: input_text.fph_voice_auth_state
        data:
          value: "verifying"

      - service: rest_command.fph_auth_verify
        data:
          home_id: "{{ states('input_text.fph_voice_auth_home_id') }}"
          response: "{{ response }}"
        response_variable: verify_response

      - choose:
          - conditions:
              - condition: template
                value_template: "{{ verify_response.content.status == 'approved' }}"
            sequence:
              - service: input_text.set_value
                target:
                  entity_id: input_text.fph_voice_auth_state
                data:
                  value: "approved"

              - service: timer.cancel
                target:
                  entity_id: timer.fph_voice_auth_timeout

              - service: scene.turn_on
                target:
                  entity_id: "scene.{{ verify_response.content.intent }}"

              - service: tts.speak
                target:
                  entity_id: media_player.satellite1_living_room
                data:
                  message: "Voice verified. {{ verify_response.content.intent | replace('_', ' ') | title }} activated."

        default:
          - service: input_text.set_value
            target:
              entity_id: input_text.fph_voice_auth_state
            data:
              value: "denied"

          - service: tts.speak
            target:
              entity_id: media_player.satellite1_living_room
            data:
              message: "{{ verify_response.content.speech }}"

          - condition: template
            value_template: "{{ verify_response.content.reason in ['no_challenge', 'expired', 'max_attempts'] }}"

          - service: timer.cancel
            target:
              entity_id: timer.fph_voice_auth_timeout

  fph_cancel_voice_auth:
    sequence:
      - service: rest_command.fph_auth_cancel
        data:
          home_id: "{{ states('input_text.fph_voice_auth_home_id') }}"

      - service: timer.cancel
        target:
          entity_id: timer.fph_voice_auth_timeout

      - service: input_text.set_value
        target:
          entity_id: input_text.fph_voice_auth_state
        data:
          value: "cancelled"

      - service: tts.speak
        target:
          entity_id: media_player.satellite1_living_room
        data:
          message: "Security check cancelled."
```

### Step 4: Create Automations

```yaml
automation:
  - id: fph_night_scene_intent
    alias: "FPH - Night Scene Intent"
    trigger:
      - platform: conversation
        command:
          - "night scene"
          - "bedtime"
          - "activate night scene"
    condition:
      - condition: state
        entity_id: input_boolean.fph_voice_auth_enabled
        state: "on"
    action:
      - service: script.fph_request_night_scene_auth

  - id: fph_response_capture
    alias: "FPH - Capture Challenge Response"
    trigger:
      - platform: conversation
        command:
          - "{response}"
    condition:
      - condition: state
        entity_id: input_text.fph_voice_auth_state
        state: "waiting_for_response"
    action:
      - service: script.fph_verify_voice_response
        data:
          response: "{{ trigger.slots.response }}"

  - id: fph_cancel_intent
    alias: "FPH - Cancel Intent"
    trigger:
      - platform: conversation
        command:
          - "cancel"
          - "never mind"
          - "stop"
    condition:
      - condition: state
        entity_id: input_text.fph_voice_auth_state
        state: "waiting_for_response"
    action:
      - service: script.fph_cancel_voice_auth

  - id: fph_timeout
    alias: "FPH - Authentication Timeout"
    trigger:
      - platform: event
        event_type: timer.finished
        event_data:
          entity_id: timer.fph_voice_auth_timeout
    action:
      - service: script.fph_cancel_voice_auth
```

---

## Testing

### Test from Command Line

```bash
# 1. Request challenge
curl -X POST http://192.168.1.100:6500/futureproofhome/auth/request \
  -H "Content-Type: application/json" \
  -d '{"home_id":"home_1","intent":"night_scene"}'

# Response: {"status":"challenge","speech":"...","challenge":"ocean four"}

# 2. Verify response
curl -X POST http://192.168.1.100:6500/futureproofhome/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"home_id":"home_1","response":"ocean four"}'

# Response: {"status":"approved","speech":"...","intent":"night_scene"}

# 3. Check status
curl http://192.168.1.100:6500/futureproofhome/auth/status
```

### Test with Home Assistant

1. Restart Home Assistant after configuration changes
2. Check Developer Tools → Services for new REST commands
3. Manually trigger `script.fph_request_night_scene_auth`
4. Listen for Satellite1 to speak the challenge
5. Speak the challenge phrase
6. Verify scene activates

---

## Configuration Options

### In config.py

```python
# Enable/disable FutureProof Homes integration
FUTUREPROOFHOME_ENABLED = True

# Default home_id if not provided
DEFAULT_HOME_ID = "home_1"

# Logging for FutureProof Homes requests
LOG_FPH_REQUESTS = True

# Challenge settings (shared with Alexa)
CHALLENGE_EXPIRY_SECONDS = 60  # Challenge timeout
MAX_ATTEMPTS = 3  # Maximum verification attempts
```

---

## Multi-Home Support

The system supports multiple homes/installations:

```yaml
# Home 1 configuration
input_text:
  fph_voice_auth_home_id_1:
    initial: home_1

# Home 2 configuration
input_text:
  fph_voice_auth_home_id_2:
    initial: home_2
```

Each `home_id` maintains independent challenge state.

---

## Troubleshooting

### "No active challenge found"

- **Cause**: Challenge expired (60 seconds) or never created
- **Solution**: Request a new challenge

### "Maximum attempts exceeded"

- **Cause**: Failed verification 3 times
- **Solution**: Request a new challenge

### "Connection refused"

- **Cause**: Orchestrator server not running or wrong IP address
- **Solution**:
  1. Verify server is running: `curl http://192.168.1.100:6500/health`
  2. Check firewall settings
  3. Verify IP address in Home Assistant configuration

### Challenge never speaks

- **Cause**: TTS not configured or wrong media_player entity
- **Solution**:
  1. Test TTS manually in Developer Tools
  2. Verify `media_player.satellite1_living_room` entity exists
  3. Check Satellite1 device is online

### Response not captured

- **Cause**: Conversation integration not working
- **Solution**:
  1. Check Home Assistant logs for conversation processing
  2. Verify custom_sentences are loaded
  3. Test with simpler utterances

---

## Security Considerations

1. **Network Security**: Orchestrator server should be on trusted network only
2. **HTTPS**: Consider using HTTPS in production (requires reverse proxy)
3. **Challenge Strength**: Default challenges use 20 words × 10 numbers = 200 combinations
4. **Time Limits**: 60-second expiry prevents replay attacks
5. **Attempt Limits**: 3 attempts maximum prevents brute force
6. **No PHI**: System transmits only generic challenge phrases

---

## Advanced Usage

### Custom Intents

Add your own protected intents:

```yaml
script:
  fph_request_lock_all_auth:
    sequence:
      - service: rest_command.fph_auth_request
        data:
          home_id: "{{ states('input_text.fph_voice_auth_home_id') }}"
          intent: "lock_all"
        response_variable: auth_response
      # ... rest of flow
```

### Dynamic Home ID Selection

Use input_select for multiple homes:

```yaml
input_select:
  active_home:
    options:
      - home_1
      - home_2
      - vacation_home

script:
  fph_request_auth_dynamic:
    sequence:
      - service: rest_command.fph_auth_request
        data:
          home_id: "{{ states('input_select.active_home') }}"
          intent: "{{ intent }}"
```

---

## Comparison: Alexa vs FutureProof Homes

| Feature | Alexa Integration | FutureProof Homes |
|---------|------------------|-------------------|
| **Privacy** | Cloud-based | 100% local |
| **Cost** | Free (requires Echo device) | $69.99 hardware |
| **Endpoint** | `/alexa` | `/futureproofhome/*` |
| **Session** | Alexa session ID | Home ID |
| **Intent Tracking** | In session context | Stored in challenge |
| **API Style** | Single webhook | RESTful API |
| **Setup** | Alexa Skills Kit required | Home Assistant only |

---

## Support

- **Issues**: Report at https://github.com/karthi1975/homeorchestrator/issues
- **FutureProof Homes**: https://futureproofhomes.net/
- **Home Assistant**: https://www.home-assistant.io/

---

## License

Same as parent project.
