#!/usr/bin/env python3
"""
MCP Server Startup Script

Run this script to start the MCP server locally.
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.software_engineer_server import SoftwareEngineerMCPServer
from agents.claude_code_agent import ClaudeCodeAgent

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('mcp_server.log')
        ]
    )

async def main():
    """Main function to start the MCP server"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Initialize the Claude Code agent
    try:
        agent = ClaudeCodeAgent()
        logger.info("Claude Code agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Claude Code agent: {e}")
        sys.exit(1)
    
    # Create and start the MCP server
    port = int(os.getenv('MCP_PORT', 8080))
    server = SoftwareEngineerMCPServer(agent=agent, port=port)
    
    logger.info(f"Starting MCP server on port {port}")
    logger.info("Server will be accessible at:")
    logger.info(f"  - Local: http://localhost:{port}")
    logger.info(f"  - Network: http://0.0.0.0:{port}")
    logger.info("\nTo connect from ChatGPT app, use the server URL above")
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

def main_console():
    """Entry point for vibeteam-mcp console script"""
    asyncio.run(main())


if __name__ == "__main__":
    main_console()
