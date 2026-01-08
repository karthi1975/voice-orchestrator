"""
FutureProof Homes voice assistant integration routes

Handles authentication requests from Home Assistant connected to
FutureProof Homes Satellite1 devices. Implements a RESTful API for
voice challenge-response authentication.

Endpoints:
- POST /futureproofhome/auth/request - Request a voice challenge
- POST /futureproofhome/auth/verify - Verify spoken response
- POST /futureproofhome/auth/cancel - Cancel pending authentication
- GET /futureproofhome/auth/status - Debug status endpoint
"""

import logging
import time
from flask import Blueprint, request, jsonify
from challenge import (
    generate_challenge,
    store_challenge,
    validate_challenge,
    clear_challenge,
    get_challenge_data,
    get_all_challenges
)
from config import CHALLENGE_EXPIRY_SECONDS, MAX_ATTEMPTS

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
futureproofhome_bp = Blueprint('futureproofhome', __name__)


@futureproofhome_bp.route('/auth/request', methods=['POST'])
def auth_request():
    """
    Request authentication challenge.

    Home Assistant calls this when a voice command requires authentication.

    Request JSON:
        {
            "home_id": "home_1",    # Unique home identifier
            "intent": "night_scene"  # Intent to execute after verification
        }

    Response JSON:
        {
            "status": "challenge",
            "speech": "Security check. Please say: ocean four",
            "challenge": "ocean four"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "Request body required"
            }), 400

        home_id = data.get('home_id')
        intent = data.get('intent')

        if not home_id:
            return jsonify({
                "error": "Missing required field: home_id"
            }), 400

        if not intent:
            return jsonify({
                "error": "Missing required field: intent"
            }), 400

        # Generate challenge
        challenge = generate_challenge()

        # Store challenge with FutureProof Homes client type and intent
        store_challenge(home_id, challenge, client_type='futureproofhome', intent=intent)

        logger.info(f"FPH auth request - home_id: {home_id}, intent: {intent}, challenge: {challenge}")

        # Build response
        response = {
            "status": "challenge",
            "speech": f"Security check. Please say: {challenge}",
            "challenge": challenge
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in FPH auth request: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error"
        }), 500


@futureproofhome_bp.route('/auth/verify', methods=['POST'])
def auth_verify():
    """
    Verify spoken challenge response.

    Home Assistant calls this with the user's spoken response to validate.

    Request JSON:
        {
            "home_id": "home_1",
            "response": "ocean four"
        }

    Success Response JSON:
        {
            "status": "approved",
            "speech": "Voice verified.",
            "intent": "night_scene"
        }

    Denied Response JSON:
        {
            "status": "denied",
            "speech": "That didn't match. Try again.",
            "reason": "mismatch",           # no_challenge | expired | max_attempts | mismatch
            "attempts_remaining": 2          # Only present for mismatch
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "Request body required"
            }), 400

        home_id = data.get('home_id')
        response_text = data.get('response')

        if not home_id:
            return jsonify({
                "error": "Missing required field: home_id"
            }), 400

        if not response_text:
            return jsonify({
                "error": "Missing required field: response"
            }), 400

        logger.info(f"FPH auth verify - home_id: {home_id}, response: {response_text}")

        # Validate challenge
        is_valid, message, intent = validate_challenge(
            home_id,
            response_text,
            client_type='futureproofhome'
        )

        if is_valid:
            # Success - return approved status with intent
            response = {
                "status": "approved",
                "speech": "Voice verified.",
                "intent": intent
            }
            logger.info(f"FPH auth approved - home_id: {home_id}, intent: {intent}")
            return jsonify(response), 200

        else:
            # Determine denial reason
            challenge_data = get_challenge_data(home_id, client_type='futureproofhome')

            if not challenge_data:
                reason = "no_challenge"
                speech = "No active challenge found. Please start over."
            elif "expired" in message.lower():
                reason = "expired"
                speech = "Challenge expired. Please start over."
            elif "maximum" in message.lower():
                reason = "max_attempts"
                speech = "Maximum attempts exceeded. Please start over."
            else:
                reason = "mismatch"
                attempts_remaining = MAX_ATTEMPTS - challenge_data.get('attempts', 0)
                speech = f"That didn't match. Try again. {attempts_remaining} attempts remaining."

            response = {
                "status": "denied",
                "speech": speech,
                "reason": reason
            }

            # Include attempts_remaining for mismatch only
            if reason == "mismatch" and challenge_data:
                response["attempts_remaining"] = MAX_ATTEMPTS - challenge_data.get('attempts', 0)

            logger.info(f"FPH auth denied - home_id: {home_id}, reason: {reason}")
            return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in FPH auth verify: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error"
        }), 500


@futureproofhome_bp.route('/auth/cancel', methods=['POST'])
def auth_cancel():
    """
    Cancel pending authentication.

    Home Assistant calls this when user cancels the authentication flow.

    Request JSON:
        {
            "home_id": "home_1"
        }

    Response JSON:
        {
            "status": "cancelled",
            "speech": "Security check cancelled."
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "error": "Request body required"
            }), 400

        home_id = data.get('home_id')

        if not home_id:
            return jsonify({
                "error": "Missing required field: home_id"
            }), 400

        # Clear the challenge
        cleared = clear_challenge(home_id, client_type='futureproofhome')

        logger.info(f"FPH auth cancel - home_id: {home_id}, cleared: {cleared}")

        response = {
            "status": "cancelled",
            "speech": "Security check cancelled."
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in FPH auth cancel: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error"
        }), 500


@futureproofhome_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """
    Get status of pending challenges.

    Debug endpoint to view all pending FutureProof Homes challenges.

    Response JSON:
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
    """
    try:
        # Get all FutureProof Homes challenges
        fpg_challenges = get_all_challenges(client_type='futureproofhome')

        current_time = time.time()
        pending_challenges = {}

        for home_id, challenge_data in fpg_challenges.items():
            elapsed = current_time - challenge_data['timestamp']
            is_expired = elapsed > CHALLENGE_EXPIRY_SECONDS

            pending_challenges[home_id] = {
                "intent": challenge_data.get('intent'),
                "attempts": challenge_data.get('attempts', 0),
                "elapsed_seconds": round(elapsed, 1),
                "expired": is_expired
            }

        response = {
            "pending_challenges": pending_challenges,
            "config": {
                "expiry_seconds": CHALLENGE_EXPIRY_SECONDS,
                "max_attempts": MAX_ATTEMPTS
            },
            "total_pending": len(pending_challenges)
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in FPH auth status: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error"
        }), 500
