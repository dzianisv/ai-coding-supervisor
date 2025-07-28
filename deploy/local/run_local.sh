#!/usr/bin/env bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting MCP Server in development mode...${NC}"

# Check if in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  No active virtual environment found. Creating one...${NC}"
    python -m venv .venv
    source .venv/bin/activate
    echo -e "✅ Created and activated virtual environment in .venv/"
else
    echo -e "✅ Using existing virtual environment at $VIRTUAL_ENV"
fi

# Install dependencies
echo -e "\n📦 Installing dependencies..."
pip install -e ".[all]"

# Set default port if not provided
export MCP_PORT=${MCP_PORT:-3333}

# Check for required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  ANTHROPIC_API_KEY environment variable is not set${NC}"
    echo -e "   You can set it with: export ANTHROPIC_API_KEY='your-api-key'"
    echo -e "   Or pass it directly: ANTHROPIC_API_KEY='your-key' $0"
    echo -e "${YELLOW}   Continuing, but the server may not work without it.${NC}"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo -e "\n🌍 Starting MCP Server on port ${MCP_PORT}..."
echo -e "   - Local:    http://localhost:${MCP_PORT}"
echo -e "   - Network:  http://$(hostname -I | awk '{print $1}'):${MCP_PORT}"
echo -e "   - API Docs: http://localhost:${MCP_PORT}/docs"
echo -e "\n🛑 Press Ctrl+C to stop the server\n"

# Run the server with hot reload
uvicorn mcp.server:app --host 0.0.0.0 --port $MCP_PORT --reload
