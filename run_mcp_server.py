#!/usr/bin/env python3
"""
MCP Server Startup Script

Run this script to start the VibeTeam MCP server using the standard MCP protocol.
"""
import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp.vibeteam_mcp_server import main_console as stdio_main

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

def main_console():
    """Entry point for vibeteam-mcp console script"""
    # Use the standard MCP protocol (stdio mode)
    stdio_main()


if __name__ == "__main__":
    main_console()