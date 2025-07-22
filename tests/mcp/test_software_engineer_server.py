"""
Tests for the Software Engineer MCP server
"""
import pytest
import json
from unittest.mock import AsyncMock
from mcp.software_engineer_server import SoftwareEngineerMCPServer

class TestSoftwareEngineerMCPServer:
    """Test cases for SoftwareEngineerMCPServer"""
    
    @pytest.fixture
    def mock_agent(self):
        return AsyncMock()
    
    @pytest.fixture
    def server(self, mock_agent):
        return SoftwareEngineerMCPServer(agent=mock_agent, port=8081)
    
    @pytest.mark.asyncio
    async def test_handle_execute_code(self, server, mock_agent):
        """Test handling of code execution"""
        # Mock the execute_task method
        mock_agent.execute_task.return_value = {
            "status": "completed",
            "output": "Hello, World!",
            "execution_time": 0.5
        }
        
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/execute",
            "params": {
                "tool": "execute_code",
                "arguments": {
                    "code": "print('Hello, World!')",
                    "language": "python"
                }
            }
        }
        
        response = await server.handle_mcp_message("session1", message)
        
        # Verify the response structure
        assert response == {
            "status": "completed",
            "result": {
                "status": "completed",
                "output": "Hello, World!",
                "execution_time": 0.5
            }
        }
        
        # Verify the code was executed with correct arguments
        mock_agent.execute_task.assert_awaited_once()
        args, _ = mock_agent.execute_task.call_args
        task = args[0]  # First positional argument is the task dict
        assert task["type"] == "execute_code"
        assert task["code"] == "print('Hello, World!')"

    @pytest.mark.asyncio
    async def test_handle_code_review(self, server, mock_agent):
        """Test handling of code review requests"""
        mock_review = {
            "status": "completed",
            "issues_found": 2,
            "feedback": "Consider adding type hints and docstrings"
        }
        mock_agent.review_work.return_value = mock_review
        
        message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/execute",
            "params": {
                "tool": "review_code",
                "arguments": {
                    "code": "def add(a, b): return a + b",
                    "language": "python"
                }
            }
        }
        
        response = await server.handle_mcp_message("session1", message)
        
        # Verify the response structure
        assert response == {
            "status": "completed",
            "result": {
                "status": "completed",
                "issues_found": 2,
                "feedback": "Consider adding type hints and docstrings"
            }
        }
        
        # Verify review_work was called with correct arguments
        mock_agent.review_work.assert_awaited_once()
        args, _ = mock_agent.review_work.call_args
        task = args[0]  # First positional argument is the task dict
        assert task["type"] == "review_code"
        assert "def add(a, b): return a + b" in task["code"]
    
    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, server):
        """Test handling of unknown tools"""
        message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/execute",
            "params": {
                "tool": "unknown_tool",
                "arguments": {}
            }
        }
        
        with pytest.raises(ValueError, match="Unknown tool: unknown_tool"):
            await server.handle_mcp_message("session1", message)
    
    @pytest.mark.asyncio
    async def test_handle_invalid_params(self, server):
        """Test handling of invalid parameters"""
        message = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/execute",
            "params": {
                "tool": "execute_code"
                # Missing required 'code' parameter
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            await server.handle_mcp_message("session1", message)
        assert "Missing required parameters: code, language" in str(exc_info.value)
