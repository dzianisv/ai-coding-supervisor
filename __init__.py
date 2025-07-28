"""
VibeTeam - AI-powered multi-agent coding tool with automated task completion.

This package provides:
- Automated task completion from tasks.md files
- Multi-agent coding workflows
- Claude Code integration
- MCP server capabilities
- Rich CLI interface
"""

__version__ = "0.1.0"
__author__ = "VibeTeam"
__email__ = "team@vibetech.co"

# Main functionality imports
from vibecode_tasks import main as run_tasks

__all__ = ["run_tasks"]