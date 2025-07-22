"""
Tests for the base MCP server implementation
"""
import pytest
import json
from unittest.mock import AsyncMock
from mcp.base_mcp_server import BaseMCPServer

class TestBaseMCPServer:
    """Test cases for BaseMCPServer"""
    
    @pytest.fixture
    def mock_agent(self):
        return AsyncMock()
    
    @pytest.fixture
    def base_server(self, mock_agent):
        return BaseMCPServer(agent=mock_agent, port=8080)
    
    @pytest.mark.asyncio
    async def test_handle_mcp_message_unknown_method(self, base_server):
        """Test handling of unknown MCP method"""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unknown/method",
            "params": {}
        }
        
        response = await base_server.handle_mcp_message("session1", message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "error" in response
        assert response["error"]["code"] == -32601  # Method not found
    
    @pytest.mark.asyncio
    async def test_format_mcp_response(self, base_server):
        """Test MCP response formatting"""
        request = {"jsonrpc": "2.0", "id": 1, "method": "test/method"}
        result = {"status": "success"}
        
        response = base_server.format_mcp_response(request, result)
        
        assert response == {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"status": "success"}
        }
    
    @pytest.mark.asyncio
    async def test_format_mcp_error(self, base_server):
        """Test MCP error formatting"""
        request = {"jsonrpc": "2.0", "id": 1, "method": "test/method"}
        error = {"code": -32000, "message": "Test error"}
        
        response = base_server.format_mcp_error(request, error)
        
        assert response == {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32000, "message": "Test error"}
        }
