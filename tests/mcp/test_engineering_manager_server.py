"""
Tests for the Engineering Manager MCP server
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from mcp.engineering_manager_server import EngineeringManagerMCPServer

class TestEngineeringManagerMCPServer:
    """Test cases for EngineeringManagerMCPServer"""
    
    @pytest.fixture
    def mock_manager(self):
        mock = AsyncMock()
        # get_team_status is a sync method, not async
        mock.get_team_status = MagicMock()
        return mock
    
    @pytest.fixture
    def server(self, mock_manager):
        return EngineeringManagerMCPServer(agent=mock_manager, port=8080)
    
    @pytest.mark.asyncio
    async def test_handle_initialize(self, server, mock_manager):
        """Test handling of initialize method"""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {}
            }
        }
        
        response = await server.handle_mcp_message("session1", message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "capabilities" in response["result"]
    
    @pytest.mark.asyncio
    async def test_handle_execute_task(self, server, mock_manager, sample_task):
        """Test handling of task execution"""
        # Mock the execute_task method
        mock_manager.execute_task.return_value = {
            "status": "completed",
            "result": "Task completed successfully"
        }
        
        message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/execute",
            "params": {
                "tool": "execute_task",
                "arguments": sample_task
            }
        }
        
        response = await server.handle_mcp_message("session1", message)
        
        # Verify the response
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert response["result"]["status"] == "completed"
        assert "result" in response["result"]
        
        # Verify the task was executed with the correct arguments
        mock_manager.execute_task.assert_awaited_once()
        args, kwargs = mock_manager.execute_task.call_args
        assert args[0] == sample_task
    
    @pytest.mark.asyncio
    async def test_handle_list_resources(self, server, mock_manager):
        """Test handling of resources/list method"""
        # Mock the get_team_status method to return test data
        mock_manager.get_team_status.return_value = {
            "team_status": {
                "agent1": {
                    "name": "Test Agent 1",
                    "status": "idle",
                    "capabilities": ["code_generation", "testing"]
                },
                "agent2": {
                    "name": "Test Agent 2",
                    "status": "busy",
                    "capabilities": ["code_review", "documentation"]
                }
            },
            "active_subtasks": 1,
            "completed_subtasks": 5,
            "task_assignments": {"task1": "agent1"}
        }
        
        message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list"
        }
        
        response = await server.handle_mcp_message("session1", message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        assert "resources" in response["result"]
        
        # Verify the response contains the expected resources
        resources = response["result"]["resources"]
        assert len(resources) >= 4  # 2 agents + 2 task queues
        
        # Verify agent resources
        agent_resources = [r for r in resources if r.get("type") == "agent"]
        assert len(agent_resources) == 2
        
        # Verify task queue resources
        queue_resources = [r for r in resources if r.get("type") == "task_queue"]
        assert len(queue_resources) == 2
    
    @pytest.mark.asyncio
    async def test_handle_read_resource(self, server, mock_manager):
        """Test handling of resources/read method"""
        # Mock the get_team_status method to return test data
        mock_manager.get_team_status.return_value = {
            "team_status": {
                "agent1": {
                    "name": "Test Agent 1",
                    "status": "idle",
                    "capabilities": ["code_generation", "testing"],
                    "current_task": None
                }
            },
            "active_subtasks": 1,
            "completed_subtasks": 5,
            "task_assignments": {"task1": "agent1"}
        }
        
        # Test reading an agent resource
        message = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {
                "uri": "agent://agent1"
            }
        }
        
        response = await server.handle_mcp_message("session1", message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 4
        assert "result" in response
        assert "contents" in response["result"]
        assert response["result"]["contents"]["name"] == "Test Agent 1"
        assert "capabilities" in response["result"]["contents"]
        
        # Test reading a task queue
        message = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {
                "uri": "tasks://active"
            }
        }
        
        response = await server.handle_mcp_message("session1", message)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 5
        assert "result" in response
        assert "contents" in response["result"]
        assert response["result"]["contents"]["status"] == "active"
        
        # Test reading a non-existent resource
        message = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/read",
            "params": {
                "uri": "invalid://resource"
            }
        }
        
        response = await server.handle_mcp_message("session1", message)
        assert "error" in response
        assert response["error"]["code"] == -32602  # Invalid params
