#!/usr/bin/env python3
"""
Multi-Agent Coding Tool - Main Entry Point
A CLI-based agentic coding tool that operates as a team of AI agents
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cli.main_cli import main_cli

if __name__ == '__main__':
    main_cli()
