"""
Flask server for Alexa Voice Authentication System
"""

from flask import Flask, render_template_string, jsonify
import logging
from config import PORT, DEBUG
from home_assistant import test_connection

# Import legacy blueprints
from routes.alexa import alexa_bp
from routes.futureproofhome import futureproofhome_bp

# Import new SOLID architecture dependency container
from app import DependencyContainer

app = Flask(__name__)

# Register legacy blueprints (backward compatibility)
app.register_blueprint(alexa_bp, url_prefix='/alexa')
app.register_blueprint(futureproofhome_bp, url_prefix='/futureproofhome')

# Register new SOLID architecture routes (parallel for testing)
# Create dependency container (without Flask app - we'll register to main app)
container = DependencyContainer()

# Register new routes with /v2 prefix for parallel testing
# Use unique names to avoid conflicts with legacy blueprints
app.register_blueprint(container.alexa_controller.blueprint, url_prefix='/alexa/v2', name='alexa_v2')
app.register_blueprint(container.fph_controller.blueprint, url_prefix='/futureproofhome/v2', name='futureproofhome_v2')
app.register_blueprint(container.admin_controller.blueprint, name='admin')

# Store container for potential access
app.container = container

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
