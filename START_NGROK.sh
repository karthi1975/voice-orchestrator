#!/bin/bash

# Quick start script for ngrok

echo "🌐 Starting ngrok tunnel for Alexa Voice Authentication"
echo "=========================================================="
echo ""
echo "Server is running on port 6500"
echo "Starting ngrok tunnel..."
echo ""
echo "IMPORTANT: Copy the HTTPS URL that appears below"
echo "Format: https://XXXXX.ngrok-free.app"
echo ""
echo "Then configure your Alexa skill endpoint:"
echo "  → Alexa Developer Console"
echo "  → Your Skill → Endpoint"
echo "  → HTTPS → https://YOUR-NGROK-URL.ngrok-free.app/alexa"
echo ""
echo "ngrok Web Interface will be available at:"
echo "  → http://127.0.0.1:4040"
echo ""
echo "=========================================================="
echo ""

ngrok http 6500
