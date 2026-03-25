import json
import urllib.request

FLASK_BASE_URL = "https://voiceorchestrator.homeadapt.us"


def lambda_handler(event, context):
    # Smart Home directives have "directive" key
    # Custom Skill requests have "session" key
    if "directive" in event:
        url = f"{FLASK_BASE_URL}/alexa/smarthome"
    else:
        url = f"{FLASK_BASE_URL}/alexa/v2"

    req = urllib.request.Request(
        url,
        data=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())
