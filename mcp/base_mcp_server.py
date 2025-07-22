"""
Base MCP Server Implementation

This module provides the base implementation of the Model Context Protocol (MCP) server.
"""
import asyncio
import json
from typing import Any, Dict, Optional, Tuple

class BaseMCPServer:
    """Base class for MCP servers"""
    
    def __init__(self, agent: Any, port: int = 8080):
        """Initialize the MCP server.
        
        Args:
            agent: The agent instance this server will expose via MCP
            port: The port number to run the server on
        """
        self.agent = agent
        self.port = port
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.server = None
    
    async def start(self):
        """Start the MCP server"""
        self.server = await asyncio.start_server(
            self._handle_connection,
            '0.0.0.0',
            self.port
        )
        
        addr = self.server.sockets[0].getsockname()
        print(f'Serving on {addr}')
        
        async with self.server:
            await self.server.serve_forever()
    
    async def _handle_connection(self, reader, writer):
        """Handle a new client connection"""
        session_id = id(reader)
        self.sessions[session_id] = {
            'reader': reader,
            'writer': writer,
            'buffer': b''
        }
        
        try:
            while True:
                # Read data from the client
                data = await reader.read(4096)
                if not data:
                    break
                
                # Process the received message
                response = await self._process_message(session_id, data)
                
                # Send the response back to the client
                if response:
                    writer.write(json.dumps(response).encode() + b'\n')
                    await writer.drain()
                    
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            # Clean up the connection
            writer.close()
            await writer.wait_closed()
            if session_id in self.sessions:
                del self.sessions[session_id]
    
    async def _process_message(self, session_id: str, data: bytes) -> Optional[Dict]:
        """Process an incoming MCP message"""
        try:
            # Parse the JSON-RPC message
            message = json.loads(data)
            
            # Handle the message based on its type
            if 'method' in message:
                # It's a request or notification
                response = await self.handle_mcp_message(session_id, message)
                
                # For notifications (no id), don't send a response
                if 'id' not in message:
                    return None
                    
                # For requests, return the response
                return response
            
            # Handle responses (shouldn't normally be received by server)
            return None
            
        except json.JSONDecodeError:
            return self.format_mcp_error(
                None,
                {"code": -32700, "message": "Parse error"}
            )
    
    async def handle_mcp_message(self, session_id: str, message: Dict) -> Dict:
        """Handle an MCP message
        
        Args:
            session_id: The ID of the client session
            message: The parsed JSON-RPC message
            
        Returns:
            A dictionary containing the JSON-RPC response
        """
        method = message.get('method', '')
        
        # Handle MCP standard methods
        if method == 'initialize':
            return await self.handle_initialize(session_id, message)
        elif method == 'shutdown':
            return await self.handle_shutdown(session_id, message)
        elif method.startswith('resources/'):
            return await self.handle_resource_method(method[10:], message)
        elif method.startswith('tools/'):
            return await self.handle_tool_method(method[6:], message)
        else:
            return self.format_mcp_error(
                message,
                {"code": -32601, "message": f"Method not found: {method}"}
            )
    
    async def handle_initialize(self, session_id: str, message: Dict) -> Dict:
        """Handle the initialize method"""
        return self.format_mcp_response(message, {
            "protocolVersion": "2025-06-18",
            "capabilities": self.get_capabilities()
        })
    
    async def handle_shutdown(self, session_id: str, message: Dict) -> Dict:
        """Handle the shutdown method"""
        if session_id in self.sessions:
            writer = self.sessions[session_id]['writer']
            writer.close()
            await writer.wait_closed()
        return self.format_mcp_response(message, {})
    
    async def handle_resource_method(self, method: str, message: Dict) -> Dict:
        """Handle resource-related methods"""
        if method == 'list':
            return await self.handle_list_resources(message)
        elif method == 'read':
            return await self.handle_read_resource(message)
        else:
            return self.format_mcp_error(
                message,
                {"code": -32601, "message": f"Unknown resource method: {method}"}
            )
    
    async def handle_tool_method(self, method: str, message: Dict) -> Dict:
        """Handle tool execution methods"""
        if method == 'execute':
            return await self.handle_execute_tool(message)
        else:
            return self.format_mcp_error(
                message,
                {"code": -32601, "message": f"Unknown tool method: {method}"}
            )
    
    async def handle_list_resources(self, message: Dict) -> Dict:
        """Handle the resources/list method"""
        resources = await self.agent.list_resources()
        return self.format_mcp_response(message, {"resources": resources})
    
    async def handle_read_resource(self, message: Dict) -> Dict:
        """Handle the resources/read method"""
        params = message.get('params', {})
        if 'uri' not in params:
            return self.format_mcp_error(
                message,
                {"code": -32602, "message": "Missing required parameter: uri"}
            )
            
        try:
            contents = await self.agent.read_resource(params['uri'])
            return self.format_mcp_response(message, {"contents": contents})
        except Exception as e:
            return self.format_mcp_error(
                message,
                {"code": -32603, "message": f"Failed to read resource: {str(e)}"}
            )
    
    async def handle_execute_tool(self, message: Dict) -> Dict:
        """Handle the tools/execute method"""
        params = message.get('params', {})
        if 'tool' not in params:
            return self.format_mcp_error(
                message,
                {"code": -32602, "message": "Missing required parameter: tool"}
            )
            
        try:
            tool_name = params['tool']
            tool_args = params.get('arguments', {})
            
            # Execute the tool with the provided arguments and message context
            response = await self.agent.execute_tool(tool_name, tool_args, message=message)
            # If the tool already formatted a complete JSON-RPC response, return it as-is
            if 'jsonrpc' in response:
                return response
            # Otherwise, format it as a standard response
            return self.format_mcp_response(message, response)
            
        except Exception as e:
            return self.format_mcp_error(
                message,
                {"code": -32000, "message": f"Tool execution failed: {str(e)}"}
            )
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get the capabilities of this MCP server"""
        return {
            "resources": {"list": True, "read": True},
            "tools": {"execute": True}
        }
    
    def format_mcp_response(self, message: Optional[Dict], result: Any) -> Dict:
        """Format a successful JSON-RPC response"""
        response = {
            "jsonrpc": "2.0",
            "result": result
        }
        
        if message and 'id' in message:
            response['id'] = message['id']
            
        return response
    
    def format_mcp_error(self, message: Optional[Dict], error: Dict) -> Dict:
        """Format a JSON-RPC error response"""
        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": error.get('code', -32000),
                "message": error.get('message', 'Unknown error')
            }
        }
        
        if 'data' in error:
            response['error']['data'] = error['data']
            
        if message and 'id' in message:
            response['id'] = message['id']
            
        return response
