"""
End-to-end tests for VibeTeam MCP Server.

These tests verify the complete MCP server functionality including:
- Server initialization and protocol compliance
- Tool execution
- Resource access
- Error handling
"""
import asyncio
import json
import pytest
import pytest_asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mcp.stdio_server import StdioMCPServer
from mcp.vibeteam_mcp_server import VibeTeamMCPServer


class MockStdin:
    """Mock stdin for testing."""
    
    def __init__(self):
        self.messages = []
        self.current = 0
        
    def add_message(self, message: dict):
        """Add a message to be read."""
        self.messages.append(json.dumps(message) + '\n')
        
    async def readline(self):
        """Read next message."""
        if self.current < len(self.messages):
            msg = self.messages[self.current].encode()
            self.current += 1
            return msg
        return b''


class MockStdout:
    """Mock stdout for capturing output."""
    
    def __init__(self):
        self.messages = []
        
    def write(self, data: str):
        """Capture written data."""
        if data.strip():
            self.messages.append(data.strip())
            
    def flush(self):
        """No-op for testing."""
        pass
        
    def get_messages(self):
        """Get all captured messages as parsed JSON."""
        return [json.loads(msg) for msg in self.messages]


@pytest.mark.asyncio
class TestStdioMCPServer:
    """Test the stdio MCP server implementation."""
    
    async def test_server_initialization(self):
        """Test server can be initialized."""
        server = StdioMCPServer(name="test-server", version="1.0.0")
        assert server.name == "test-server"
        assert server.version == "1.0.0"
        assert len(server.tools) == 0
        assert len(server.resources) == 0
        
    async def test_initialize_request(self):
        """Test initialize request handling."""
        server = StdioMCPServer(name="test-server", version="1.0.0")
        
        # Test initialize request
        response = await server._handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert response["result"]["serverInfo"]["name"] == "test-server"
        assert response["result"]["serverInfo"]["version"] == "1.0.0"
        
    async def test_tool_registration_and_listing(self):
        """Test tool registration and listing."""
        server = StdioMCPServer()
        
        # Register a test tool
        async def test_handler(param1: str, param2: int = 42):
            return {"result": f"{param1}-{param2}"}
            
        server.add_tool(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "integer"}
                },
                "required": ["param1"]
            },
            handler=test_handler
        )
        
        # List tools
        response = await server._handle_message({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        
        assert response["result"]["tools"][0]["name"] == "test_tool"
        assert response["result"]["tools"][0]["description"] == "A test tool"
        
    async def test_tool_execution(self):
        """Test tool execution."""
        server = StdioMCPServer()
        
        # Register a test tool
        async def test_handler(message: str):
            return {"processed": message.upper()}
            
        server.add_tool(
            name="uppercase",
            description="Convert to uppercase",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            },
            handler=test_handler
        )
        
        # Execute tool
        response = await server._handle_message({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "uppercase",
                "arguments": {"message": "hello"}
            }
        })
        
        assert response["result"]["content"][0]["type"] == "text"
        assert '"processed": "HELLO"' in response["result"]["content"][0]["text"]
        
    async def test_resource_handling(self):
        """Test resource registration and reading."""
        server = StdioMCPServer()
        
        # Register a test resource
        async def test_resource_handler():
            return "Test resource content"
            
        server.add_resource(
            uri="test://resource",
            name="Test Resource",
            description="A test resource",
            handler=test_resource_handler
        )
        
        # List resources
        list_response = await server._handle_message({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {}
        })
        
        assert list_response["result"]["resources"][0]["uri"] == "test://resource"
        assert list_response["result"]["resources"][0]["name"] == "Test Resource"
        
        # Read resource
        read_response = await server._handle_message({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "test://resource"}
        })
        
        assert read_response["result"]["contents"][0]["text"] == "Test resource content"
        
    async def test_error_handling(self):
        """Test error handling."""
        server = StdioMCPServer()
        
        # Test unknown method
        response = await server._handle_message({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "unknown/method",
            "params": {}
        })
        
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]
        
        # Test invalid JSON (via direct error response creation)
        error_response = server._error_response(None, -32700, "Parse error")
        assert error_response["error"]["code"] == -32700
        assert error_response["error"]["message"] == "Parse error"


@pytest.mark.asyncio
class TestVibeTeamMCPServer:
    """Test the VibeTeam MCP server implementation."""
    
    @pytest_asyncio.fixture
    async def server(self, tmp_path):
        """Create a test server instance."""
        server = VibeTeamMCPServer(working_directory=str(tmp_path))
        yield server
        
    async def test_server_initialization(self, server):
        """Test VibeTeam server initialization."""
        assert server.working_directory is not None
        assert server.server.name == "vibeteam"
        assert server.server.version == "1.0.0"
        
    async def test_registered_tools(self, server):
        """Test that all expected tools are registered."""
        expected_tools = [
            "execute_task",
            "review_code",
            "generate_code",
            "fix_code",
            "write_tests",
            "complete_tasks",
            "manage_project"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in server.server.tools
            
    async def test_registered_resources(self, server):
        """Test that all expected resources are registered."""
        expected_resources = [
            "workspace:///",
            "workspace:///tasks.md",
            "agent:///status"
        ]
        
        for resource_uri in expected_resources:
            assert resource_uri in server.server.resources
            
    @patch('mcp.vibeteam_mcp_server.ClaudeCodeAgent')
    async def test_execute_task_tool(self, mock_agent_class, server):
        """Test execute_task tool."""
        # Mock the agent
        mock_agent = AsyncMock()
        mock_agent.execute_task = AsyncMock(return_value={"status": "completed"})
        mock_agent_class.return_value = mock_agent
        
        # Execute task
        result = await server._handle_execute_task(
            description="Test task",
            working_directory=server.working_directory
        )
        
        assert result["status"] == "success"
        assert "result" in result
        mock_agent.execute_task.assert_called_once()
        
    @patch('mcp.vibeteam_mcp_server.ClaudeCodeAgent')
    async def test_review_code_tool(self, mock_agent_class, server):
        """Test review_code tool."""
        # Mock the agent
        mock_agent = AsyncMock()
        mock_agent.review_work = AsyncMock(return_value={
            "issues": [],
            "suggestions": ["Good code!"]
        })
        mock_agent_class.return_value = mock_agent
        
        # Review code
        result = await server._handle_review_code(
            code="def hello(): pass",
            language="python"
        )
        
        assert result["status"] == "success"
        assert "review" in result
        mock_agent.review_work.assert_called_once()
        
    async def test_workspace_resource(self, server, tmp_path):
        """Test workspace resource reading."""
        # Create some test files
        (tmp_path / "test.py").write_text("print('hello')")
        (tmp_path / "data.json").write_text("{}")
        
        # Read workspace resource
        content = await server._handle_workspace_resource()
        
        assert "Files in workspace:" in content
        assert "test.py" in content
        assert "data.json" in content
        
    async def test_agent_status_resource(self, server):
        """Test agent status resource."""
        content = await server._handle_agent_status_resource()
        
        assert "Working Directory:" in content
        assert "Claude Code Agent: Not initialized" in content
        assert "Engineering Manager: Not initialized" in content
        
    async def test_tasks_resource_missing(self, server):
        """Test tasks resource when tasks.md doesn't exist."""
        content = await server._handle_tasks_resource()
        assert "No tasks.md file found" in content
        
    async def test_tasks_resource_exists(self, server, tmp_path):
        """Test tasks resource when tasks.md exists."""
        tasks_content = "[ ] Task 1\n[x] Task 2\n"
        (tmp_path / "tasks.md").write_text(tasks_content)
        
        content = await server._handle_tasks_resource()
        assert content == tasks_content


@pytest.mark.asyncio
class TestMCPProtocolIntegration:
    """Integration tests for full MCP protocol flow."""
    
    async def test_full_protocol_flow(self, tmp_path):
        """Test a complete MCP protocol interaction."""
        # Create server
        server = VibeTeamMCPServer(working_directory=str(tmp_path))
        
        # Mock stdin/stdout
        mock_stdin = MockStdin()
        mock_stdout = MockStdout()
        
        # Add test messages
        mock_stdin.add_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        
        mock_stdin.add_message({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        
        # Patch stdin/stdout
        with patch('sys.stdin', mock_stdin), patch('sys.stdout', mock_stdout):
            # Run server briefly
            server_task = asyncio.create_task(server.server._read_loop())
            await asyncio.sleep(0.1)
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
                
        # Check responses
        messages = mock_stdout.get_messages()
        assert len(messages) >= 2
        
        # Check initialize response
        init_response = messages[0]
        assert init_response["result"]["serverInfo"]["name"] == "vibeteam"
        
        # Check tools list response
        tools_response = messages[1]
        assert len(tools_response["result"]["tools"]) > 0
        
    @patch('mcp.vibeteam_mcp_server.ClaudeCodeAgent')
    async def test_tool_execution_flow(self, mock_agent_class, tmp_path):
        """Test tool execution through the protocol."""
        # Create server
        server = VibeTeamMCPServer(working_directory=str(tmp_path))
        
        # Mock agent
        mock_agent = AsyncMock()
        mock_agent.execute_task = AsyncMock(return_value={"output": "Task completed"})
        mock_agent_class.return_value = mock_agent
        
        # Execute tool through server protocol
        response = await server.server._handle_message({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "execute_task",
                "arguments": {
                    "description": "Test task execution"
                }
            }
        })
        
        assert response["id"] == 10
        assert "result" in response
        assert "content" in response["result"]


class TestCloudflareIntegration:
    """Test Cloudflare tunnel integration."""
    
    def test_cloudflare_script_exists(self):
        """Test that Cloudflare setup script exists."""
        script_path = project_root / "deploy" / "cloudflare" / "setup_tunnel.sh"
        assert script_path.exists()
        assert script_path.stat().st_mode & 0o111  # Check executable
        
    def test_cloudflare_readme_exists(self):
        """Test that Cloudflare documentation exists."""
        readme_path = project_root / "deploy" / "cloudflare" / "README.md"
        assert readme_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])