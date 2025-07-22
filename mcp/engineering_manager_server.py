"""
Engineering Manager MCP Server

This module provides the MCP server implementation for the Engineering Manager agent.
"""
import asyncio
from typing import Any, Dict, Optional, List

from .base_mcp_server import BaseMCPServer

class EngineeringManagerMCPServer(BaseMCPServer):
    """MCP server for the Engineering Manager agent"""
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get the capabilities of this MCP server"""
        return {
            "resources": {
                "list": True,
                "read": True,
                "write": False
            },
            "tools": {
                "execute": True,
                "task_management": True,
                "code_review": True,
                "project_planning": True
            },
            "agent": {
                "type": "engineering_manager",
                "version": "1.0.0"
            }
        }
    
    async def handle_execute_tool(self, message: Dict) -> Dict:
        """Handle the tools/execute method"""
        params = message.get('params', {})
        tool_name = params.get('tool')
        arguments = params.get('arguments', {})
        
        if not tool_name:
            return self.format_mcp_error(
                message,
                {"code": -32602, "message": "Missing required parameter: tool"}
            )
        
        try:
            # Handle different tool types
            if tool_name == "execute_task":
                result = await self.agent.execute_task(arguments)
                return self.format_mcp_response(message, {
                    "status": "completed",
                    "result": result
                })
                
            elif tool_name == "review_work":
                if 'work_item' not in arguments:
                    return self.format_mcp_error(
                        message,
                        {"code": -32602, "message": "Missing required parameter: work_item"}
                    )
                
                review = await self.agent.review_work(arguments['work_item'])
                return self.format_mcp_response(message, {
                    "status": "completed",
                    "review": review
                })
                
            elif tool_name == "get_team_status":
                status = self.agent.get_team_status()
                return self.format_mcp_response(message, {
                    "status": "completed",
                    "team_status": status
                })
                
            else:
                return self.format_mcp_error(
                    message,
                    {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                )
                
        except Exception as e:
            return self.format_mcp_error(
                message,
                {
                    "code": -32000,
                    "message": f"Tool execution failed: {str(e)}",
                    "data": {"tool": tool_name}
                }
            )
    
    async def handle_list_resources(self, message: Dict) -> Dict:
        """Handle the resources/list method"""
        try:
            # Get the list of available agents as resources
            team_status = self.agent.get_team_status()
            resources = [
                {
                    "uri": f"agent://{agent_id}",
                    "type": "agent",
                    "name": agent_info["name"],
                    "status": agent_info["status"],
                    "capabilities": agent_info["capabilities"]
                }
                for agent_id, agent_info in team_status.get("team_status", {}).items()
            ]
            
            # Add the task queue as a resource
            resources.append({
                "uri": "tasks://active",
                "type": "task_queue",
                "count": team_status.get("active_subtasks", 0),
                "status": "active"
            })
            
            resources.append({
                "uri": "tasks://completed",
                "type": "task_queue",
                "count": team_status.get("completed_subtasks", 0),
                "status": "completed"
            })
            
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
            # Handle agent resource URIs
            if uri.startswith("agent://"):
                agent_id = uri[8:]  # Remove 'agent://' prefix
                team_status = self.agent.get_team_status()
                
                if agent_id not in team_status.get("team_status", {}):
                    return self.format_mcp_error(
                        message,
                        {"code": -32602, "message": f"Agent not found: {agent_id}"}
                    )
                
                agent_info = team_status["team_status"][agent_id]
                return self.format_mcp_response(message, {
                    "contents": agent_info,
                    "metadata": {
                        "type": "agent",
                        "uri": uri
                    }
                })
            
            # Handle task queue URIs
            elif uri.startswith("tasks://"):
                queue_type = uri[8:]  # Remove 'tasks://' prefix
                team_status = self.agent.get_team_status()
                
                if queue_type == "active":
                    return self.format_mcp_response(message, {
                        "contents": {
                            "status": "active",
                            "count": team_status.get("active_subtasks", 0),
                            "tasks": list(team_status.get("task_assignments", {}).items())
                        },
                        "metadata": {
                            "type": "task_queue",
                            "uri": uri
                        }
                    })
                
                elif queue_type == "completed":
                    return self.format_mcp_response(message, {
                        "contents": {
                            "status": "completed",
                            "count": team_status.get("completed_subtasks", 0)
                        },
                        "metadata": {
                            "type": "task_queue",
                            "uri": uri
                        }
                    })
                
                else:
                    return self.format_mcp_error(
                        message,
                        {"code": -32602, "message": f"Unknown task queue: {queue_type}"}
                    )
            
            else:
                return self.format_mcp_error(
                    message,
                    {"code": -32602, "message": f"Unsupported resource URI: {uri}"}
                )
                
        except Exception as e:
            return self.format_mcp_error(
                message,
                {"code": -32603, "message": f"Failed to read resource: {str(e)}"}
            )
