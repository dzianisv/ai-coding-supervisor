"""
Software Engineer MCP Server

This module provides the MCP server implementation for the Software Engineer agent.
"""
import asyncio
import logging
from typing import Any, Dict, Optional, List

from .base_mcp_server import BaseMCPServer

class SoftwareEngineerMCPServer(BaseMCPServer):
    """MCP server for the Software Engineer (Claude Code) agent"""
    
    def __init__(self, agent, port=8080):
        """Initialize the Software Engineer MCP server.
        
        Args:
            agent: The agent instance to use for executing tasks
            port: The port number to run the server on (default: 8080)
        """
        super().__init__(agent=agent, port=port)
        self.logger = logging.getLogger(__name__)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get the capabilities of this MCP server"""
        return {
            "resources": {
                "list": True,
                "read": True,
                "write": True
            },
            "tools": {
                "execute": True,
                "code_generation": True,
                "code_review": True,
                "code_editing": True,
                "testing": True,
                "debugging": True
            },
            "agent": {
                "type": "software_engineer",
                "version": "1.0.0"
            },
            "languages": ["python", "javascript", "typescript", "java", "c++", "go", "rust"]
        }
    
    async def handle_execute_tool(self, message: Dict) -> Dict:
        """Handle the tools/execute method"""
        try:
            params = message.get('params', {})
            tool_name = params.get('tool')
            arguments = params.get('arguments', {})
            
            if not tool_name:
                raise ValueError("Missing required parameter: tool")
            
            # Execute the tool with the provided arguments
            result = await self.execute_tool(tool_name, arguments)
            return result
            
        except Exception as e:
            # Log the error and re-raise to be handled by the base server
            self.logger.error(f"Error in handle_execute_tool: {str(e)}", exc_info=True)
            raise
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute a tool with the given name and arguments.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool
            **kwargs: Additional keyword arguments
            
        Returns:
            Dictionary with the result of the tool execution
        """
        try:
            # Get the method that handles this tool
            tool_method_name = f"_handle_{tool_name}"
            if not hasattr(self, tool_method_name):
                error_msg = f"Unknown tool: {tool_name}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            tool_method = getattr(self, tool_method_name)
            
            # Get the method signature to check for required parameters
            import inspect
            sig = inspect.signature(tool_method)
            
            # Check for missing required arguments
            bound_arguments = sig.bind_partial()
            bound_arguments.apply_defaults()
            
            # Get required parameters (those without defaults)
            required_params = [
                param.name for param in sig.parameters.values()
                if param.default == inspect.Parameter.empty 
                and param.name != 'self' 
                and param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            ]
            
            # Check if all required parameters are provided
            missing_params = [p for p in required_params if p not in arguments]
            if missing_params:
                error_msg = f"Missing required parameters: {', '.join(missing_params)}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Call the tool method with the provided arguments
            result = await tool_method(**{k: v for k, v in arguments.items() if k in sig.parameters})
            
            # Return the result dictionary (will be wrapped in JSON-RPC by the base server)
            return {
                "status": "completed",
                "result": result
            }
            
        except Exception as e:
            # Log the error and re-raise to be handled by the base server
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
            raise
    
    async def _handle_execute_code(self, code: str, language: str, **kwargs) -> Dict:
        """Handle code execution requests
        
        Args:
            code: The code to execute
            language: The programming language of the code
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Dict containing the execution result
        """
        # Execute the code using the Claude agent
        task = {
            "type": "execute_code",
            "code": code,
            "language": language
        }
        
        return await self.agent.execute_task(task)
    
    async def _handle_review_code(self, code: str, language: str, **kwargs) -> Dict:
        """Handle code review requests
        
        Args:
            code: The code to review
            language: The programming language of the code
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Dict containing the review result
        """
        # Review the code using the Claude agent
        task = {
            "type": "review_code",
            "code": code,
            "language": language
        }
        
        return await self.agent.review_work(task)
    
    async def _handle_generate_code(self, **kwargs) -> Dict:
        """Handle code generation requests"""
        required_params = ["specification", "language"]
        self._validate_parameters(kwargs, required_params)
        
        # Generate code using the Claude agent
        task = {
            "type": "generate_code",
            "specification": kwargs["specification"],
            "language": kwargs["language"]
        }
        
        result = await self.agent.execute_task(task)
        return result
    
    async def _handle_edit_code(self, **kwargs) -> Dict:
        """Handle code editing requests"""
        required_params = ["code", "instructions", "language"]
        self._validate_parameters(kwargs, required_params)
        
        # Edit code using the Claude agent
        task = {
            "type": "edit_code",
            "code": kwargs["code"],
            "instructions": kwargs["instructions"],
            "language": kwargs["language"]
        }
        
        result = await self.agent.execute_task(task)
        return result
    
    async def _handle_write_tests(self, **kwargs) -> Dict:
        """Handle test writing requests"""
        required_params = ["code", "language", "test_framework"]
        self._validate_parameters(kwargs, required_params)
        
        # Write tests using the Claude agent
        task = {
            "type": "write_tests",
            "code": kwargs["code"],
            "language": kwargs["language"],
            "test_framework": kwargs["test_framework"]
        }
        
        result = await self.agent.execute_task(task)
        return result
    
    async def _handle_debug_code(self, **kwargs) -> Dict:
        """Handle code debugging requests"""
        required_params = ["code", "error_message", "language"]
        self._validate_parameters(kwargs, required_params)
        
        # Debug code using the Claude agent
        task = {
            "type": "debug_code",
            "code": kwargs["code"],
            "error_message": kwargs["error_message"],
            "language": kwargs["language"]
        }
        
        # Execute the task
        result = await self.agent.execute_task(task)
        
        # Format the response
        return self.format_mcp_response(message, {
            "status": "completed",
            "debug_info": result
        })
    
    async def handle_list_resources(self, message: Dict) -> Dict:
        """Handle the resources/list method"""
        try:
            # For the Software Engineer agent, we can list available files in the workspace
            # or other relevant resources
            resources = [
                {
                    "uri": "workspace:///current_file",
                    "type": "file",
                    "name": "Current File",
                    "language": "python"
                },
                {
                    "uri": "workspace:///test_cases",
                    "type": "directory",
                    "name": "Test Cases"
                },
                {
                    "uri": "workspace:///documentation",
                    "type": "directory",
                    "name": "Documentation"
                }
            ]
            
            return self.format_mcp_response(message, {"resources": resources})
            
        except Exception as e:
            return self.format_mcp_error(
                message,
                {"code": -32603, "message": f"Failed to list resources: {str(e)}"}
            )
    
    async def handle_read_resource(self, message: Dict) -> Dict:
        """Handle the resources/read method"""
        params = message.get('params', {})
        uri = params.get('uri')
        
        if not uri:
            return self.format_mcp_error(
                message,
                {"code": -32602, "message": "Missing required parameter: uri"}
            )
        
        try:
            # In a real implementation, this would read from the actual workspace
            # For now, we'll return a mock response
            if uri == "workspace:///current_file":
                return self.format_mcp_response(message, {
                    "contents": "# Sample Python file\n\ndef hello_world():\n    return 'Hello, World!'\n",
                    "metadata": {
                        "type": "file",
                        "language": "python",
                        "uri": uri
                    }
                })
            
            else:
                return self.format_mcp_error(
                    message,
                    {"code": -32602, "message": f"Resource not found: {uri}"}
                )
                
        except Exception as e:
            return self.format_mcp_error(
                message,
                {"code": -32603, "message": f"Failed to read resource: {str(e)}"}
            )
