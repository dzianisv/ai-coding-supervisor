"""
MCP Server implementation using stdio transport (standard MCP protocol).

This module provides a proper MCP server that communicates via stdin/stdout
following the Model Context Protocol specification.
"""
import asyncio
import json
import sys
import logging
from typing import Any, Dict, Optional, List, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class StdioMCPServer:
    """MCP Server that communicates via stdin/stdout."""
    
    def __init__(self, name: str = "vibeteam-mcp", version: str = "1.0.0"):
        """Initialize the MCP server.
        
        Args:
            name: Server name
            version: Server version
        """
        self.name = name
        self.version = version
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._read_task = None
        self._message_id_counter = 0
        
    def add_tool(self, name: str, description: str, parameters: Dict[str, Any], 
                 handler: Callable) -> None:
        """Register a tool with the server.
        
        Args:
            name: Tool name
            description: Tool description
            parameters: JSON Schema for tool parameters
            handler: Async function to handle tool execution
        """
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": parameters,
            "handler": handler
        }
        
    def add_resource(self, uri: str, name: str, description: str,
                    handler: Callable) -> None:
        """Register a resource with the server.
        
        Args:
            uri: Resource URI
            name: Resource name
            description: Resource description
            handler: Async function to read the resource
        """
        self.resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "handler": handler
        }
        
    async def start(self) -> None:
        """Start the MCP server."""
        self._running = True
        logger.info(f"Starting {self.name} MCP server v{self.version}")
        
        # Start reading messages from stdin
        self._read_task = asyncio.create_task(self._read_loop())
        
        try:
            await self._read_task
        except asyncio.CancelledError:
            logger.info("Server shutdown")
            
    async def stop(self) -> None:
        """Stop the MCP server."""
        self._running = False
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
                
    async def _read_loop(self) -> None:
        """Read messages from stdin."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        
        try:
            # Get the event loop
            loop = asyncio.get_event_loop()
            
            # For subprocess communication, stdin might be a pipe
            # which requires different handling
            await loop.connect_read_pipe(
                lambda: protocol, sys.stdin
            )
            
            while self._running:
                # Read line from stdin
                line = await reader.readline()
                if not line:
                    break
                    
                try:
                    # Parse JSON-RPC message
                    message = json.loads(line.decode('utf-8').strip())
                    
                    # Process message
                    response = await self._handle_message(message)
                    
                    # Send response if not a notification
                    if response is not None:
                        await self._send_message(response)
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    error_response = self._error_response(
                        None, -32700, "Parse error"
                    )
                    await self._send_message(error_response)
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Read loop error: {e}", exc_info=True)
            
    async def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to stdout.
        
        Args:
            message: Message to send
        """
        try:
            json_str = json.dumps(message, separators=(',', ':'))
            sys.stdout.write(json_str + '\n')
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            
    async def _handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle an incoming message.
        
        Args:
            message: Incoming JSON-RPC message
            
        Returns:
            Response message or None for notifications
        """
        # Check if it's a request
        if "method" not in message:
            return None
            
        method = message["method"]
        params = message.get("params", {})
        message_id = message.get("id")
        
        try:
            # Route to appropriate handler
            if method == "initialize":
                result = await self._handle_initialize(params)
            elif method == "tools/list":
                result = await self._handle_tools_list(params)
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "resources/list":
                result = await self._handle_resources_list(params)
            elif method == "resources/read":
                result = await self._handle_resources_read(params)
            elif method == "completion/complete":
                result = await self._handle_completion(params)
            else:
                # Unknown method
                if message_id is not None:
                    return self._error_response(
                        message_id, -32601, f"Method not found: {method}"
                    )
                return None
                
            # Return response if this was a request (has id)
            if message_id is not None:
                return self._success_response(message_id, result)
                
        except Exception as e:
            logger.error(f"Error handling {method}: {e}", exc_info=True)
            if message_id is not None:
                return self._error_response(
                    message_id, -32603, f"Internal error: {str(e)}"
                )
                
        return None
        
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
                "completion": {}
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version
            }
        }
        
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = []
        for tool_name, tool_info in self.tools.items():
            tools.append({
                "name": tool_info["name"],
                "description": tool_info["description"],
                "inputSchema": tool_info["inputSchema"]
            })
        return {"tools": tools}
        
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        if not tool_name or tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        tool = self.tools[tool_name]
        handler = tool["handler"]
        tool_params = params.get("arguments", {})
        
        # Execute tool
        result = await handler(**tool_params)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                }
            ]
        }
        
    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources = []
        for uri, resource_info in self.resources.items():
            resources.append({
                "uri": resource_info["uri"],
                "name": resource_info["name"],
                "description": resource_info["description"]
            })
        return {"resources": resources}
        
    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")
        if not uri or uri not in self.resources:
            raise ValueError(f"Unknown resource: {uri}")
            
        resource = self.resources[uri]
        handler = resource["handler"]
        
        # Read resource
        content = await handler()
        
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": content
                }
            ]
        }
        
    async def _handle_completion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completion request."""
        # For now, return empty completion
        return {
            "completion": {
                "values": []
            }
        }
        
    def _success_response(self, message_id: Any, result: Any) -> Dict[str, Any]:
        """Create a success response."""
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": result
        }
        
    def _error_response(self, message_id: Any, code: int, message: str,
                       data: Any = None) -> Dict[str, Any]:
        """Create an error response."""
        error = {
            "code": code,
            "message": message
        }
        if data is not None:
            error["data"] = data
            
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": error
        }