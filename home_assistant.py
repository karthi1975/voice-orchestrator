"""
Home Assistant integration for triggering scenes via webhook
"""

import requests
from typing import Tuple
from datetime import datetime
from config import HA_URL, HA_WEBHOOK_ID, TEST_MODE


def trigger_scene(scene_name: str) -> Tuple[bool, str]:
    """
    Trigger a Home Assistant scene via webhook.

    Args:
        scene_name: Name of the scene to trigger (e.g., "night_scene")

    Returns:
        Tuple of (success, message)
    """
    # TEST MODE: Just log to console instead of calling Home Assistant
    if TEST_MODE:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scene_display = scene_name.replace('_', ' ').title()

        print("\n" + "="*60)
        print(f"🏠 HOME ASSISTANT SCENE TRIGGER")
        print("="*60)
        print(f"Timestamp:    {timestamp}")
        print(f"Scene:        {scene_display}")
        print(f"Scene ID:     {scene_name}")
        print(f"Source:       Alexa Voice Authentication")
        print(f"Status:       ✓ SUCCESS")
        print("="*60 + "\n")

        return True, f"{scene_display} activated successfully"

    # PRODUCTION MODE: Actually call Home Assistant
    webhook_url = f"{HA_URL}/api/webhook/{HA_WEBHOOK_ID}"

    payload = {
        "scene": scene_name,
        "source": "alexa_voice_auth"
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            return True, f"{scene_name.replace('_', ' ').title()} activated successfully"
        else:
            return False, f"Home Assistant returned status {response.status_code}"

    except requests.exceptions.Timeout:
        return False, "Home Assistant connection timed out"

    except requests.exceptions.ConnectionError:
        return False, "Could not connect to Home Assistant. Please check if it's running."

    except Exception as e:
        return False, f"Error triggering scene: {str(e)}"


def test_connection() -> Tuple[bool, str]:
    """
    Test connection to Home Assistant.

    Returns:
        Tuple of (success, message)
    """
    # TEST MODE: Skip connection test
    if TEST_MODE:
        return True, "Running in TEST MODE (Home Assistant connection disabled)"

    # PRODUCTION MODE: Actually test connection
    try:
        response = requests.get(
            f"{HA_URL}/api/",
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            return True, f"Connected to Home Assistant: {data.get('message', 'OK')}"
        else:
            return False, f"Home Assistant returned status {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, "Could not connect to Home Assistant. Check HA_URL in config.py"

    except Exception as e:
        return False, f"Connection test failed: {str(e)}"
