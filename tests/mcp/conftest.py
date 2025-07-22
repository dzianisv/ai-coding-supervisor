"""
Pytest configuration and fixtures for MCP server tests
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.engineering_manager import EngineeringManager
from agents.claude_code_agent import ClaudeCodeAgent

@pytest.fixture
def mock_engineering_manager():
    """Fixture providing a mock EngineeringManager"""
    manager = AsyncMock(spec=EngineeringManager)
    manager.agent_id = "eng_manager_1"
    manager.name = "Test Engineering Manager"
    manager.status = "idle"
    return manager

@pytest.fixture
def mock_claude_agent():
    """Fixture providing a mock ClaudeCodeAgent"""
    agent = AsyncMock(spec=ClaudeCodeAgent)
    agent.agent_id = "claude_agent_1"
    agent.name = "Test Claude Agent"
    agent.status = "idle"
    return agent

@pytest.fixture
def sample_mcp_message():
    """Sample MCP message for testing"""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {}
        }
    }

@pytest.fixture
def sample_task():
    """Sample task for testing"""
    return {
        "id": "task_123",
        "description": "Write a function to calculate factorial",
        "language": "python"
    }
