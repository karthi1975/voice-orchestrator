"""
Alexa Skill integration routes

Handles all Alexa requests including:
- Launch requests
- Intent requests (Night Scene, Challenge Response, Help, etc.)
- Session end requests
"""

import logging
from flask import Blueprint, request, jsonify
from challenge import generate_challenge, store_challenge, validate_challenge, clear_expired_challenges
from home_assistant import trigger_scene

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
alexa_bp = Blueprint('alexa', __name__)


@alexa_bp.route('', methods=['POST'])
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

    # Validate the response (intent is not needed for Alexa, context is in session)
    is_valid, message, _ = validate_challenge(session_id, spoken_response)

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
