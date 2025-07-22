"""
Integration tests for MCP servers
"""
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch
from pathlib import Path
import json
import pytest_asyncio

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from mcp.engineering_manager_server import EngineeringManagerMCPServer
from mcp.software_engineer_server import SoftwareEngineerMCPServer
from agents.engineering_manager import EngineeringManager
from agents.claude_code_agent import ClaudeCodeAgent

class TestMCPIntegration:
    """Integration tests for MCP servers with real agents"""
    
    @pytest_asyncio.fixture
    async def setup_servers(self):
        """Set up test environment with both MCP servers"""
        # Create real agents
        eng_manager = EngineeringManager("test_eng_manager", production=False)
        claude_agent = ClaudeCodeAgent("test_claude_agent")
        
        # Register Claude agent with Engineering Manager
        eng_manager.register_agent(claude_agent)
        
        # Create MCP servers
        eng_server = EngineeringManagerMCPServer(eng_manager, port=8080)
        se_server = SoftwareEngineerMCPServer(claude_agent, port=8081)
        
        # Start servers in the background
        eng_task = asyncio.create_task(eng_server.start())
        se_task = asyncio.create_task(se_server.start())
        
        # Give servers a moment to start
        await asyncio.sleep(0.1)
        
        try:
            yield eng_server, se_server, eng_manager, claude_agent
        finally:
            # Cleanup
            eng_task.cancel()
            se_task.cancel()
            try:
                await asyncio.gather(eng_task, se_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, setup_servers):
        """Test complete workflow from task submission to completion"""
        eng_server, se_server, eng_manager, claude_agent = setup_servers
        
        # Sample task for the Engineering Manager
        task = {
            "id": "test_task_1",
            "description": "Write a Python function that adds two numbers",
            "language": "python"
        }
        
        # Mock the Claude agent's response
        mock_result = {
            "status": "completed",
            "output": "def add(a, b):\n    return a + b",
            "execution_time": 0.5
        }
        
        # Patch the Claude agent's execute_task method
        with patch.object(claude_agent, 'execute_task', 
                         new_callable=AsyncMock, 
                         return_value=mock_result) as mock_execute:
            
            # Simulate MCP message to Engineering Manager
            message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/execute",
                "params": {
                    "tool": "execute_task",
                    "arguments": task
                }
            }
            
            # Send message to Engineering Manager MCP server
            response = await eng_server.handle_mcp_message("test_session", message)
            
            # Verify response
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert "result" in response
            assert response["result"]["status"] == "completed"
            
            # Verify Claude agent was called
            mock_execute.assert_awaited_once()
            
            # Verify the task was assigned and completed
            assert eng_manager.completed_subtasks
            subtask_id = next(iter(eng_manager.completed_subtasks))
            assert eng_manager.completed_subtasks[subtask_id]["result"]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_direct_claude_agent_interaction(self, setup_servers):
        """Test direct interaction with the Software Engineer MCP server"""
        _, se_server, _, claude_agent = setup_servers
        
        # Mock the Claude agent's response
        mock_result = {
            "status": "completed",
            "output": "Hello, World!",
            "execution_time": 0.1
        }
        
        # Patch the Claude agent's execute_task method
        with patch.object(claude_agent, 'execute_task', 
                         new_callable=AsyncMock, 
                         return_value=mock_result) as mock_execute:
            
            # Simulate MCP message to Software Engineer MCP server
            message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/execute",
                "params": {
                    "tool": "execute_task",
                    "arguments": {
                        "task_id": "test_task_1",
                        "description": "Test task",
                        "requirements": ["test"],
                        "priority": 1
                    }
                }
            }
            
            # Send message to Software Engineer MCP server
            response = await se_server.handle_mcp_message("test_session", message)
            
            # Verify response
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 2
            assert "result" in response
            assert response["result"]["status"] == "completed"
            assert "Hello, World!" in response["result"]["output"]
            
            # Verify Claude agent was called
            mock_execute.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, setup_servers):
        """Test error handling in the MCP servers"""
        eng_server, se_server, _, _ = setup_servers
        
        # Test invalid JSON-RPC message
        invalid_message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "nonexistent/method"
        }
        
        # Send to Engineering Manager
        eng_response = await eng_server.handle_mcp_message("test_session", invalid_message)
        assert "error" in eng_response
        assert eng_response["error"]["code"] == -32601  # Method not found
        
        # Send to Software Engineer
        se_response = await se_server.handle_mcp_message("test_session", invalid_message)
        assert "error" in se_response
        assert se_response["error"]["code"] == -32601  # Method not found
