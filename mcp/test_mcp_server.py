#!/usr/bin/env python3
"""
Test MCP server that doesn't require API keys.
Used for E2E testing of Cloudflare tunnel integration.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.base_mcp_server import BaseMCPServer
from mcp.stdio_server import StdioMCPServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockAgent:
    """Mock agent for testing without API keys."""
    
    def __init__(self, working_directory: str = None):
        self.working_directory = working_directory or "."
        
    async def execute_task(self, task_description: str) -> Dict[str, Any]:
        """Mock task execution."""
        return {
            "status": "completed",
            "output": f"Mock execution of: {task_description}",
            "files_created": [],
            "files_modified": []
        }
    
    def review_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Mock code review."""
        return {
            "status": "completed",
            "review": "Mock review: Code looks good!",
            "suggestions": ["This is a mock review"]
        }
    
    def generate_code(self, specification: str, language: str = "python") -> Dict[str, Any]:
        """Mock code generation."""
        return {
            "status": "completed",
            "code": f"# Mock generated code for: {specification}\ndef hello():\n    return 'Hello from mock!'",
            "language": language
        }


class TestMCPServer:
    """Test MCP server without API key requirements."""
    
    def __init__(self, working_directory: Optional[str] = None):
        self.working_directory = working_directory or "."
        self.agent = MockAgent(self.working_directory)
        
        # Initialize stdio server
        self.server = StdioMCPServer(
            name="test-vibeteam",
            version="1.0.0",
            capabilities={
                "agent": {
                    "type": "vibeteam-test",
                    "version": "1.0.0",
                    "capabilities": ["code_generation", "code_review", "task_execution"]
                }
            }
        )
        
        # Register tools
        self._register_tools()
        
        # Register resources
        self._register_resources()
        
    def _register_tools(self) -> None:
        """Register test tools."""
        # Execute task tool
        self.server.add_tool(
            name="execute_task",
            description="Execute a mock task (no API key required)",
            parameters={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Task description"
                    }
                },
                "required": ["description"]
            },
            handler=self._handle_execute_task
        )
        
        # Review code tool
        self.server.add_tool(
            name="review_code",
            description="Review code (mock)",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to review"
                    }
                },
                "required": ["code"]
            },
            handler=self._handle_review_code
        )
        
        # Generate code tool
        self.server.add_tool(
            name="generate_code",
            description="Generate code (mock)",
            parameters={
                "type": "object",
                "properties": {
                    "specification": {
                        "type": "string",
                        "description": "Code specification"
                    }
                },
                "required": ["specification"]
            },
            handler=self._handle_generate_code
        )
    
    def _register_resources(self) -> None:
        """Register test resources."""
        self.server.add_resource(
            uri="test://status",
            name="Test Status",
            description="Current test server status",
            handler=self._handle_status_resource
        )
        
        self.server.add_resource(
            uri="test://workspace",
            name="Test Workspace",
            description="Test workspace information",
            handler=self._handle_workspace_resource
        )
    
    async def _handle_execute_task(self, **params) -> Dict[str, Any]:
        """Handle task execution."""
        try:
            result = await self.agent.execute_task(params["description"])
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    async def _handle_review_code(self, **params) -> Dict[str, Any]:
        """Handle code review."""
        try:
            result = self.agent.review_code(params["code"])
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    async def _handle_generate_code(self, **params) -> Dict[str, Any]:
        """Handle code generation."""
        try:
            result = self.agent.generate_code(params["specification"])
            return result
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    async def _handle_status_resource(self, uri: str) -> Dict[str, Any]:
        """Handle status resource."""
        return {
            "content": {
                "status": "running",
                "mode": "test",
                "agent": "mock",
                "api_keys_required": False
            }
        }
    
    async def _handle_workspace_resource(self, uri: str) -> Dict[str, Any]:
        """Handle workspace resource."""
        return {
            "content": {
                "working_directory": self.working_directory,
                "test_mode": True
            }
        }
    
    async def run(self):
        """Run the test server."""
        logger.info("Starting Test MCP Server (no API keys required)...")
        await self.server.run()


async def main():
    """Main entry point."""
    import os
    working_dir = os.getenv("VIBETEAM_WORKING_DIR", ".")
    
    server = TestMCPServer(working_directory=working_dir)
    await server.run()


# Also support TCP mode for testing
class TestTCPMCPServer(BaseMCPServer):
    """Test TCP MCP server."""
    
    def __init__(self, port: int = 3333):
        self.agent = MockAgent()
        super().__init__(agent=self.agent, port=port)
        
        # Override capabilities
        self.server_info["capabilities"]["agent"] = {
            "type": "vibeteam-test-tcp",
            "version": "1.0.0",
            "capabilities": ["code_generation", "code_review", "task_execution"]
        }
    
    async def handle_execute_code(self, message: Dict) -> Dict:
        """Handle code execution."""
        params = message.get("params", {})
        result = await self.agent.execute_task(params.get("code", ""))
        return self.format_mcp_response(message, result)
    
    async def handle_generate_code(self, message: Dict) -> Dict:
        """Handle code generation."""
        params = message.get("params", {})
        result = self.agent.generate_code(params.get("specification", ""))
        return self.format_mcp_response(message, result)


async def main_tcp():
    """Main entry point for TCP mode."""
    import os
    port = int(os.getenv("MCP_PORT", 3333))
    
    server = TestTCPMCPServer(port=port)
    logger.info(f"Starting Test TCP MCP Server on port {port} (no API keys required)...")
    await server.start()


if __name__ == "__main__":
    import os
    
    mode = os.getenv("MCP_MODE", "stdio")
    
    if mode == "tcp":
        asyncio.run(main_tcp())
    else:
        asyncio.run(main())