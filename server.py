"""
Flask server for Alexa Voice Authentication System
"""

from flask import Flask, request, jsonify, render_template_string
import logging
from config import PORT, DEBUG
from challenge import generate_challenge, store_challenge, validate_challenge, clear_expired_challenges
from home_assistant import trigger_scene, test_connection

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Simple dashboard HTML
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Alexa Voice Auth - Home Assistant</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
        }
        .status {
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }
        .success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
        }
        ul {
            line-height: 1.8;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 Alexa Voice Authentication</h1>
        <p>Home Assistant Scene Control with Voice Security</p>

        <div class="status info">
            <strong>Server Status:</strong> Running on port {{ port }}
        </div>

        <h2>How to Use</h2>
        <ol>
            <li>Say: <code>"Alexa, open home security"</code></li>
            <li>Say: <code>"night scene"</code></li>
            <li>Alexa will give you a challenge phrase</li>
            <li>Repeat the exact phrase</li>
            <li>If correct, Home Assistant scene activates</li>
        </ol>

        <h2>Configuration</h2>
        <ul>
            <li><strong>Home Assistant URL:</strong> {{ ha_url }}</li>
            <li><strong>Webhook ID:</strong> {{ webhook_id }}</li>
            <li><strong>Alexa Endpoint:</strong> /alexa</li>
        </ul>

        <h2>Setup Steps</h2>
        <ol>
            <li>Use ngrok to expose this server: <code>ngrok http {{ port }}</code></li>
            <li>Configure Alexa skill endpoint with ngrok URL + /alexa</li>
            <li>Set up Home Assistant webhook automation</li>
            <li>Test with Alexa app or device</li>
        </ol>
    </div>
</body>
</html>
"""


@app.route('/')
def index():
    """Dashboard page"""
    from config import HA_URL, HA_WEBHOOK_ID
    return render_template_string(
        DASHBOARD_HTML,
        port=PORT,
        ha_url=HA_URL,
        webhook_id=HA_WEBHOOK_ID
    )


@app.route('/alexa', methods=['POST'])
def alexa_webhook():
    """
    Main Alexa webhook handler.
    Processes all Alexa requests and returns appropriate responses.
    """
    try:
        request_data = request.get_json()
        logger.info(f"Received Alexa request: {request_data.get('request', {}).get('type')}")

        # Extract request details
        request_type = request_data.get('request', {}).get('type')
        intent_name = request_data.get('request', {}).get('intent', {}).get('name')
        session_id = request_data.get('session', {}).get('sessionId')

        # Clean up expired challenges periodically
        clear_expired_challenges()

        # Route to appropriate handler
        if request_type == 'LaunchRequest':
            return handle_launch()

        elif request_type == 'IntentRequest':
            if intent_name == 'NightSceneIntent':
                return handle_night_scene_intent(session_id)

            elif intent_name == 'ChallengeResponseIntent':
                return handle_challenge_response(request_data, session_id)

            elif intent_name == 'AMAZON.HelpIntent':
                return handle_help()

            elif intent_name in ['AMAZON.StopIntent', 'AMAZON.CancelIntent']:
                return handle_stop()

            elif intent_name == 'AMAZON.FallbackIntent':
                return handle_fallback()

        elif request_type == 'SessionEndedRequest':
            return handle_session_end()

        # Unknown request type
        return build_response("I didn't understand that. Please try again.")

    except Exception as e:
        logger.error(f"Error processing Alexa request: {str(e)}", exc_info=True)
        return build_response("Sorry, there was an error processing your request.")


def handle_launch():
    """Handle skill launch"""
    speech = "Home security activated. Say night scene to begin."
    return build_response(speech, should_end_session=False)


def handle_night_scene_intent(session_id):
    """Handle night scene activation request"""
    challenge = generate_challenge()
    store_challenge(session_id, challenge)

    speech = f"Security check required. Please say: {challenge}"
    return build_response(speech, should_end_session=False)


def handle_challenge_response(request_data, session_id):
    """Handle user's challenge response"""
    # Extract the spoken response
    slots = request_data.get('request', {}).get('intent', {}).get('slots', {})
    response_slot = slots.get('response', {})
    spoken_response = response_slot.get('value', '')

    logger.info(f"Challenge response: {spoken_response}")

    # Validate the response
    is_valid, message = validate_challenge(session_id, spoken_response)

    if is_valid:
        # Trigger Home Assistant scene
        success, ha_message = trigger_scene('night_scene')

        if success:
            speech = "Voice verified. Night scene activated."
        else:
            speech = f"Voice verified, but scene activation failed: {ha_message}"

        return build_response(speech, should_end_session=True)
    else:
        speech = f"{message} Please try saying night scene again if you want to retry."
        return build_response(speech, should_end_session=False)


def handle_help():
    """Handle help request"""
    speech = ("This skill controls your Home Assistant with voice authentication. "
              "Say night scene, then repeat the security phrase I give you. "
              "What would you like to do?")
    return build_response(speech, should_end_session=False)


def handle_stop():
    """Handle stop/cancel request"""
    speech = "Home security deactivated. Goodbye."
    return build_response(speech, should_end_session=True)


def handle_fallback():
    """Handle fallback intent"""
    speech = ("I didn't understand. You can say night scene to activate the night scene. "
              "What would you like to do?")
    return build_response(speech, should_end_session=False)


def handle_session_end():
    """Handle session end"""
    return build_response("", should_end_session=True)


def build_response(speech_text, should_end_session=True):
    """
    Build an Alexa response.

    Args:
        speech_text: Text for Alexa to speak
        should_end_session: Whether to end the session

    Returns:
        JSON response for Alexa
    """
    return jsonify({
        'version': '1.0',
        'response': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': speech_text
            },
            'shouldEndSession': should_end_session
        }
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    ha_status, ha_message = test_connection()
    return jsonify({
        'status': 'healthy',
        'home_assistant': {
            'connected': ha_status,
            'message': ha_message
        }
    })


if __name__ == '__main__':
    logger.info(f"Starting Alexa Voice Authentication Server on port {PORT}")
    logger.info("Testing Home Assistant connection...")

    # Test Home Assistant connection on startup
    success, message = test_connection()
    if success:
        logger.info(f"✓ {message}")
    else:
        logger.warning(f"✗ {message}")
        logger.warning("Server will start anyway, but Home Assistant integration may not work.")

    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
