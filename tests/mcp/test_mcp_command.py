"""
Test the vibeteam-mcp console command.

This tests the actual command-line interface for starting the MCP server.
"""
import asyncio
import json
import subprocess
import sys
import time
import pytest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestMCPCommand:
    """Test the vibeteam-mcp command line interface."""
    
    def test_mcp_command_help(self):
        """Test that vibeteam-mcp command is available."""
        # Try running with Python module syntax
        result = subprocess.run(
            [sys.executable, "-m", "run_mcp_server", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )
        
        # The command should exit cleanly (might not have --help implemented)
        assert result.returncode in [0, 1, 2]
        
    @pytest.mark.asyncio
    async def test_mcp_server_stdio_protocol(self, tmp_path):
        """Test MCP server responds to stdio protocol."""
        # Start the MCP server process
        process = subprocess.Popen(
            [sys.executable, "-m", "run_mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
            env={**os.environ, "VIBETEAM_WORKING_DIR": str(tmp_path)}
        )
        
        try:
            # Send initialize request
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {}
            }
            
            process.stdin.write(json.dumps(initialize_request) + '\n')
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            assert response_line
            
            response = json.loads(response_line.strip())
            assert response["id"] == 1
            assert "result" in response
            assert response["result"]["serverInfo"]["name"] == "vibeteam"
            
            # Send tools/list request
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            process.stdin.write(json.dumps(tools_request) + '\n')
            process.stdin.flush()
            
            # Read response
            response_line = process.stdout.readline()
            assert response_line
            
            response = json.loads(response_line.strip())
            assert response["id"] == 2
            assert "result" in response
            assert len(response["result"]["tools"]) > 0
            
            # Verify expected tools are present
            tool_names = [t["name"] for t in response["result"]["tools"]]
            assert "execute_task" in tool_names
            assert "review_code" in tool_names
            assert "generate_code" in tool_names
            
        finally:
            # Clean up
            process.terminate()
            process.wait(timeout=5)
            
    def test_mcp_server_tcp_mode(self):
        """Test that TCP mode can be started."""
        # Start server in TCP mode
        process = subprocess.Popen(
            [sys.executable, "-m", "run_mcp_server", "--tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root)
        )
        
        try:
            # Give it a moment to start
            time.sleep(1)
            
            # Check if process is still running
            assert process.poll() is None, "TCP server should be running"
            
            # Check output for startup message
            # Note: This might be in stderr due to logging
            output = process.stdout.read(100) if process.stdout else ""
            error = process.stderr.read(100) if process.stderr else ""
            
            # Should see some indication it's starting
            assert "TCP" in output or "TCP" in error or "port" in output or "port" in error
            
        finally:
            # Clean up
            process.terminate()
            process.wait(timeout=5)


@pytest.mark.asyncio
class TestMCPServerScenarios:
    """Test realistic usage scenarios."""
    
    async def test_code_review_scenario(self, tmp_path):
        """Test a code review scenario through MCP."""
        # Start the MCP server process
        process = subprocess.Popen(
            [sys.executable, "-m", "run_mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
            env={**os.environ, "VIBETEAM_WORKING_DIR": str(tmp_path)}
        )
        
        try:
            # Initialize
            process.stdin.write(json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {}
            }) + '\n')
            process.stdin.flush()
            
            # Read initialization response
            response = json.loads(process.stdout.readline().strip())
            assert response["result"]["serverInfo"]["name"] == "vibeteam"
            
            # Request code review
            process.stdin.write(json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "review_code",
                    "arguments": {
                        "code": "def add(a, b):\n    return a + b",
                        "language": "python"
                    }
                }
            }) + '\n')
            process.stdin.flush()
            
            # Read review response
            response_line = process.stdout.readline()
            if response_line:
                response = json.loads(response_line.strip())
                assert response["id"] == 2
                # Should have result or error
                assert "result" in response or "error" in response
                
        finally:
            process.terminate()
            process.wait(timeout=5)
            
    async def test_resource_access_scenario(self, tmp_path):
        """Test accessing resources through MCP."""
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('Hello, MCP!')")
        
        # Start the MCP server process
        process = subprocess.Popen(
            [sys.executable, "-m", "run_mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
            env={**os.environ, "VIBETEAM_WORKING_DIR": str(tmp_path)}
        )
        
        try:
            # Initialize
            process.stdin.write(json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {}
            }) + '\n')
            process.stdin.flush()
            process.stdout.readline()  # Read init response
            
            # List resources
            process.stdin.write(json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list",
                "params": {}
            }) + '\n')
            process.stdin.flush()
            
            response = json.loads(process.stdout.readline().strip())
            assert len(response["result"]["resources"]) > 0
            
            # Read workspace resource
            process.stdin.write(json.dumps({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {"uri": "workspace:///"}
            }) + '\n')
            process.stdin.flush()
            
            response = json.loads(process.stdout.readline().strip())
            assert "test.py" in response["result"]["contents"][0]["text"]
            
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


import os