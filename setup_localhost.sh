#!/bin/bash
# MCP Server Localhost Setup Script

set -e

echo "🚀 Setting up MCP Server for localhost hosting..."

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
echo "✓ Python version: $python_version"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# Create logs directory
mkdir -p logs

# Make run script executable
chmod +x run_mcp_server.py

echo "✅ Setup complete!"
echo ""
echo "🎯 To start the MCP server:"
echo "   python3 run_mcp_server.py"
echo ""
echo "🌐 Server will be available at:"
echo "   - Local: http://localhost:8080"
echo "   - Network: http://0.0.0.0:8080"
echo ""
echo "🔗 For external access (e.g., ChatGPT app), consider using ngrok:"
echo "   1. Install ngrok: brew install ngrok (macOS) or download from ngrok.com"
echo "   2. Run: ngrok http 8080"
echo "   3. Use the ngrok URL in your ChatGPT app configuration"
echo ""
echo "📝 Logs will be saved to: mcp_server.log"
